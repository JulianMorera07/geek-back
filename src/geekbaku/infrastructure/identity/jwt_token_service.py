"""JWT Authentication: implementación concreta de
`application.identity.ports.TokenService` con `PyJWT`.

Refresh tokens NO son JWT: son secretos aleatorios opacos
(`secrets.token_urlsafe`), hasheados con SHA-256 antes de persistirse
(igual razón que un password hash: si la tabla se filtra, no debe filtrar
tokens usables). SHA-256 simple alcanza acá — a diferencia de un password,
un refresh token ya es alta entropía por construcción, no necesita un
hash lento tipo Argon2/bcrypt.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from geekbaku.application.identity.mappers import parse_user_id
from geekbaku.domain.identity.exceptions import AuthenticationError
from geekbaku.domain.identity.value_objects import Identity
from geekbaku.domain.shared.errors import ValidationError


class JwtTokenService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_ttl_seconds: int = 900,
        refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_ttl = access_token_ttl_seconds
        self._refresh_ttl = refresh_token_ttl_seconds

    def issue_access_token(self, identity: Identity) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._access_ttl)
        payload = {
            "sub": str(identity.user_id),
            "email": identity.email,
            "roles": sorted(identity.roles),
            "permissions": sorted(identity.permissions),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid4()),
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token, self._access_ttl

    def decode_access_token(self, token: str) -> Identity:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("El access token expiró.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("El access token es inválido.") from exc

        try:
            user_id = parse_user_id(payload["sub"])
        except (KeyError, ValidationError) as exc:
            raise AuthenticationError("El access token tiene claims inválidos.") from exc

        return Identity(
            user_id=user_id,
            email=payload.get("email", ""),
            roles=frozenset(payload.get("roles", ())),
            permissions=frozenset(payload.get("permissions", ())),
        )

    def generate_refresh_token_value(self) -> str:
        return secrets.token_urlsafe(48)

    def hash_refresh_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def refresh_token_ttl_seconds(self) -> int:
        return self._refresh_ttl


__all__ = ["JwtTokenService"]
