"""Caso de uso: login. Orquesta Authentication Provider (estrategia
'password' por defecto) + Brute Force Guard + creación de Session +
emisión de AccessToken/RefreshToken.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from geekbaku.application.identity.dto import AccessTokenDTO, AuthResultDTO, LoginCommand
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import build_identity, user_to_dto
from geekbaku.application.identity.ports import BruteForceGuard, IdentityUnitOfWork, TokenService
from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.domain.identity.entities import RefreshToken, Session
from geekbaku.domain.identity.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    TooManyAttemptsError,
)
from geekbaku.domain.identity.value_objects import RefreshTokenId, SessionId

DEFAULT_PROVIDER_ID = "password"


class LoginUser:
    def __init__(
        self,
        uow: IdentityUnitOfWork,
        provider_registry: AuthenticationProviderRegistry,
        token_service: TokenService,
        brute_force_guard: BruteForceGuard,
    ) -> None:
        self._uow = uow
        self._providers = provider_registry
        self._tokens = token_service
        self._guard = brute_force_guard

    async def execute(self, command: LoginCommand) -> AuthResultDTO:
        guard_key = f"{command.email.strip().lower()}:{command.ip_address or 'unknown'}"

        if await self._guard.is_blocked(guard_key):
            raise TooManyAttemptsError(
                "Demasiados intentos fallidos de login. Intentá de nuevo más tarde."
            )

        provider = self._providers.get(DEFAULT_PROVIDER_ID)
        try:
            user = await provider.authenticate(
                {"email": command.email, "password": command.password}, self._uow
            )
        except InvalidCredentialsError:
            await self._guard.register_failure(guard_key)
            raise

        await self._guard.register_success(guard_key)

        if not user.is_active:
            raise InactiveUserError(f"El usuario {user.id} está desactivado.")

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        identity = build_identity(user, roles, permissions)

        now = datetime.now(UTC)
        refresh_ttl = self._tokens.refresh_token_ttl_seconds()
        session = Session(
            id=SessionId.new(),
            user_id=user.id,
            expires_at=now + timedelta(seconds=refresh_ttl),
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        await self._uow.sessions.add(session)

        raw_refresh_token = self._tokens.generate_refresh_token_value()
        refresh_token = RefreshToken(
            id=RefreshTokenId.new(),
            user_id=user.id,
            session_id=session.id,
            token_hash=self._tokens.hash_refresh_token(raw_refresh_token),
            expires_at=now + timedelta(seconds=refresh_ttl),
        )
        await self._uow.refresh_tokens.add(refresh_token)

        access_token_value, expires_in = self._tokens.issue_access_token(identity)

        return AuthResultDTO(
            access_token=AccessTokenDTO(
                value=access_token_value, token_type="bearer", expires_in=expires_in
            ),
            refresh_token=raw_refresh_token,
            user=user_to_dto(user, roles=roles, permissions=permissions),
        )
