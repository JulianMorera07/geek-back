"""Primera estrategia de autenticación: email + password.

Implementa `application.identity.ports.AuthenticationProvider`. Una
estrategia nueva (Google/GitHub OAuth, magic-link, WebAuthn, ...) se
agrega escribiendo otra clase que implemente el mismo Protocol y
registrándola en `AuthenticationProviderRegistry` — nunca tocando esta
clase, `LoginUser`, ni el dominio.
"""

from __future__ import annotations

from collections.abc import Mapping

from geekbaku.application.identity.ports import IdentityUnitOfWork, PasswordHasher
from geekbaku.domain.identity.entities import User
from geekbaku.domain.identity.exceptions import InvalidCredentialsError
from geekbaku.domain.identity.value_objects import Email
from geekbaku.domain.shared.errors import ValidationError


class PasswordAuthenticationProvider:
    provider_id = "password"

    def __init__(self, password_hasher: PasswordHasher) -> None:
        self._hasher = password_hasher

    async def authenticate(
        self, credentials: Mapping[str, str], uow: IdentityUnitOfWork
    ) -> User:
        email_value = credentials.get("email", "")
        password = credentials.get("password", "")

        try:
            email = Email(email_value)
        except ValidationError as exc:
            raise InvalidCredentialsError("Email o contraseña incorrectos.") from exc

        user = await uow.users.get_by_email(str(email))
        if user is None:
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        credential = await uow.credentials.get_by_user_and_provider(user.id, self.provider_id)
        if credential is None or credential.secret_hash is None:
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        if not self._hasher.verify(password, credential.secret_hash):
            raise InvalidCredentialsError("Email o contraseña incorrectos.")

        return user


__all__ = ["PasswordAuthenticationProvider"]
