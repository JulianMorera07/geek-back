"""Caso de uso: refrescar el AccessToken usando un RefreshToken.

Implementa Token Rotation: cada uso de un refresh token lo invalida y
emite uno nuevo. Si el token presentado ya fue rotado antes
(`RefreshToken.rotate` levanta `RefreshTokenReusedError`), se interpreta
como evidencia de robo y se revoca TODA la sesión (todos los refresh
tokens emitidos bajo ella) — no solo se rechaza el pedido.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from geekbaku.application.identity.dto import AccessTokenDTO, AuthResultDTO, RefreshTokenCommand
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import build_identity, user_to_dto
from geekbaku.application.identity.ports import IdentityUnitOfWork, TokenService
from geekbaku.domain.identity.entities import RefreshToken
from geekbaku.domain.identity.exceptions import (
    InactiveUserError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReusedError,
    RefreshTokenRevokedError,
    SessionExpiredError,
    SessionRevokedError,
    UserNotFoundError,
)
from geekbaku.domain.identity.value_objects import RefreshTokenId, SessionId


class RefreshAccessToken:
    def __init__(self, uow: IdentityUnitOfWork, token_service: TokenService) -> None:
        self._uow = uow
        self._tokens = token_service

    async def execute(self, command: RefreshTokenCommand) -> AuthResultDTO:
        token_hash = self._tokens.hash_refresh_token(command.refresh_token)
        token = await self._uow.refresh_tokens.get_by_hash(token_hash)
        if token is None:
            raise RefreshTokenNotFoundError("El refresh token no existe.")

        if token.is_rotated:
            await self._revoke_session_chain(token.session_id)
            raise RefreshTokenReusedError(
                f"El refresh token {token.id} ya había sido usado: se revocó la sesión completa."
            )
        if token.is_revoked:
            raise RefreshTokenRevokedError(f"El refresh token {token.id} fue revocado.")
        if token.is_expired():
            raise RefreshTokenExpiredError(f"El refresh token {token.id} expiró.")

        session = await self._uow.sessions.get_by_id(token.session_id)
        if session is None or session.is_revoked:
            raise SessionRevokedError(f"La sesión {token.session_id} fue revocada.")
        if session.is_expired():
            raise SessionExpiredError(f"La sesión {token.session_id} expiró.")

        user = await self._uow.users.get_by_id(token.user_id)
        if user is None:
            raise UserNotFoundError(f"No existe el usuario {token.user_id}.")
        if not user.is_active:
            raise InactiveUserError(f"El usuario {user.id} está desactivado.")

        now = datetime.now(UTC)
        refresh_ttl = self._tokens.refresh_token_ttl_seconds()

        new_raw_token = self._tokens.generate_refresh_token_value()
        new_token = RefreshToken(
            id=RefreshTokenId.new(),
            user_id=user.id,
            session_id=session.id,
            token_hash=self._tokens.hash_refresh_token(new_raw_token),
            expires_at=now + timedelta(seconds=refresh_ttl),
        )
        token.rotate(new_token.id, now=now)
        await self._uow.refresh_tokens.update(token)
        await self._uow.refresh_tokens.add(new_token)

        session.touch(now=now)
        await self._uow.sessions.update(session)

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        identity = build_identity(user, roles, permissions)
        access_token_value, expires_in = self._tokens.issue_access_token(identity)

        return AuthResultDTO(
            access_token=AccessTokenDTO(
                value=access_token_value, token_type="bearer", expires_in=expires_in
            ),
            refresh_token=new_raw_token,
            user=user_to_dto(user, roles=roles, permissions=permissions),
        )

    async def _revoke_session_chain(self, session_id: SessionId) -> None:
        session = await self._uow.sessions.get_by_id(session_id)
        if session is not None and not session.is_revoked:
            session.revoke()
            await self._uow.sessions.update(session)
        for token in await self._uow.refresh_tokens.list_by_session(session_id):
            if not token.is_revoked:
                token.revoke()
                await self._uow.refresh_tokens.update(token)
