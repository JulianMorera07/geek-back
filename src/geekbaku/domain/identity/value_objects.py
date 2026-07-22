"""Value Objects del módulo de identidad.

Deliberadamente sin ninguna dependencia hacia `domain.catalog`,
`domain.providers` ni `domain.playback`: identidad debe poder evolucionar
(o reemplazarse) sin arrastrar ni ser arrastrada por el resto del dominio.
La única dependencia es `domain.shared.errors`, igual que cualquier otro
módulo de dominio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from geekbaku.domain.shared.errors import ValidationError

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def _new_uuid() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Identidades tipadas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserId:
    value: UUID

    @staticmethod
    def new() -> UserId:
        return UserId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class RoleId:
    value: UUID

    @staticmethod
    def new() -> RoleId:
        return RoleId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class PermissionId:
    value: UUID

    @staticmethod
    def new() -> PermissionId:
        return PermissionId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class CredentialId:
    value: UUID

    @staticmethod
    def new() -> CredentialId:
        return CredentialId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SessionId:
    value: UUID

    @staticmethod
    def new() -> SessionId:
        return SessionId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class RefreshTokenId:
    value: UUID

    @staticmethod
    def new() -> RefreshTokenId:
        return RefreshTokenId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Value Objects con validación
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValidationError(f"'{self.value}' no es un email válido.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Username:
    value: str

    def __post_init__(self) -> None:
        if not _USERNAME_PATTERN.match(self.value):
            raise ValidationError(
                "El username debe tener entre 3 y 32 caracteres "
                "(letras, números, '.', '_' o '-')."
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Profile:
    """Datos de presentación de un usuario. Se reemplaza como un todo
    (`User.update_profile`), nunca se mutan campos individuales — mismo
    patrón que `playback.WatchProgress` dentro de `PlaybackSession`.
    """

    display_name: str = ""
    avatar_url: str | None = None
    bio: str = ""

    def __post_init__(self) -> None:
        if len(self.bio) > 500:
            raise ValidationError("La bio no puede superar los 500 caracteres.")


@dataclass(frozen=True, slots=True)
class UserSettings:
    """Preferencias de usuario. Igual que `Profile`, se reemplaza entera."""

    language: str = "es"
    theme: str = "system"
    notifications_enabled: bool = True

    def __post_init__(self) -> None:
        if self.theme not in {"light", "dark", "system"}:
            raise ValidationError(f"Theme '{self.theme}' inválido (light/dark/system).")


@dataclass(frozen=True, slots=True)
class Identity:
    """El principal autenticado en tiempo de ejecución — derivado de un
    `AccessToken` válido, NO la entidad `User` persistida.

    Esta distinción es intencional: `User` es el agregado de persistencia
    (fuente de verdad, se lee/escribe en `IdentityRepository`); `Identity`
    es una foto inmutable de sus claims (roles/permisos ya resueltos) tal
    como quedaron grabados en el token en el momento en que se emitió. Todo
    el `AuthorizationService` opera sobre `Identity`, nunca necesita volver
    a golpear el repositorio para autorizar un pedido.
    """

    user_id: UserId
    email: str
    roles: frozenset[str]
    permissions: frozenset[str]
    is_active: bool = True

    def has_role(self, name: str) -> bool:
        return name in self.roles

    def has_permission(self, resource: str, action: str) -> bool:
        return f"{resource}:{action}" in self.permissions


__all__ = [
    "CredentialId",
    "Email",
    "Identity",
    "PermissionId",
    "Profile",
    "RefreshTokenId",
    "RoleId",
    "SessionId",
    "UserId",
    "UserSettings",
    "Username",
]
