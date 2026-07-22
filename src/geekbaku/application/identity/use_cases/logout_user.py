"""Caso de uso: logout. Revoca el refresh token presentado y toda la
sesión asociada (y, con ella, cualquier otro refresh token vivo bajo esa
sesión) — un logout es una revocación completa, no solo "olvidar" un token.
"""

from __future__ import annotations

from geekbaku.application.identity.dto import LogoutCommand
from geekbaku.application.identity.ports import IdentityUnitOfWork, TokenService
from geekbaku.domain.identity.exceptions import RefreshTokenNotFoundError


class LogoutUser:
    def __init__(self, uow: IdentityUnitOfWork, token_service: TokenService) -> None:
        self._uow = uow
        self._tokens = token_service

    async def execute(self, command: LogoutCommand) -> None:
        token_hash = self._tokens.hash_refresh_token(command.refresh_token)
        token = await self._uow.refresh_tokens.get_by_hash(token_hash)
        if token is None:
            raise RefreshTokenNotFoundError("El refresh token no existe.")

        session = await self._uow.sessions.get_by_id(token.session_id)
        if session is not None and not session.is_revoked:
            session.revoke()
            await self._uow.sessions.update(session)

        for session_token in await self._uow.refresh_tokens.list_by_session(token.session_id):
            if not session_token.is_revoked:
                session_token.revoke()
                await self._uow.refresh_tokens.update(session_token)
