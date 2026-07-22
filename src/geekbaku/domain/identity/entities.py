"""Entidades del módulo de identidad.

`User` es el Aggregate Root de la persistencia de identidad. `Credential`,
`Session` y `RefreshToken` son entidades propias con su propio ciclo de
vida (no sub-entidades de `User`: se persisten y consultan por su cuenta,
igual que `Role`/`Permission`) — evita que `User` crezca sin límite y
permite que un usuario tenga múltiples sesiones/credenciales concurrentes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from geekbaku.domain.identity.exceptions import RefreshTokenReusedError
from geekbaku.domain.identity.value_objects import (
    CredentialId,
    Email,
    PermissionId,
    Profile,
    RefreshTokenId,
    RoleId,
    SessionId,
    UserId,
    Username,
    UserSettings,
)


class Permission:
    """Un permiso atómico: la capacidad de ejecutar `action` sobre
    `resource` (ej. resource="anime", action="read"). `key` es el string
    que efectivamente viaja en el `AccessToken` y contra el que
    `AuthorizationService` compara.
    """

    def __init__(
        self, id: PermissionId, resource: str, action: str, description: str = ""
    ) -> None:
        self.id = id
        self.resource = resource
        self.action = action
        self.description = description

    @property
    def key(self) -> str:
        return f"{self.resource}:{self.action}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Permission) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Role:
    """Un rol agrupa permisos (RBAC). `is_system` protege roles base
    (`user`, `admin`) de ser borrados desde la API en un sprint futuro.
    """

    def __init__(
        self,
        id: RoleId,
        name: str,
        permission_ids: set[PermissionId] | None = None,
        is_system: bool = False,
    ) -> None:
        self.id = id
        self.name = name
        self.permission_ids = set(permission_ids or set())
        self.is_system = is_system

    def grant(self, permission_id: PermissionId) -> None:
        self.permission_ids.add(permission_id)

    def revoke(self, permission_id: PermissionId) -> None:
        self.permission_ids.discard(permission_id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Role) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Credential:
    """Un método de autenticación asociado a un `User`.

    `provider_id` identifica QUÉ `AuthenticationProvider` la emitió
    ("password" hoy; "google"/"github"/etc. en un sprint futuro sin tocar
    esta entidad). `secret_hash` es el hash de una contraseña (estrategia
    "password"); `external_subject` es el id externo de un proveedor
    federado (estrategia OAuth-like) — un `Credential` usa uno u otro,
    nunca ambos.
    """

    def __init__(
        self,
        id: CredentialId,
        user_id: UserId,
        provider_id: str,
        secret_hash: str | None = None,
        external_subject: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.provider_id = provider_id
        self.secret_hash = secret_hash
        self.external_subject = external_subject
        self.created_at = created_at or datetime.now(UTC)

    def rotate_secret(self, new_secret_hash: str) -> None:
        self.secret_hash = new_secret_hash

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Credential) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Session:
    """Una sesión de autenticación (creada en login, cerrada en logout o
    por expiración). Agrupa uno o más `RefreshToken` — revocar la sesión
    revoca toda la cadena de tokens emitidos bajo ella (ver
    `RefreshAccessToken`/`LogoutUser`).
    """

    def __init__(
        self,
        id: SessionId,
        user_id: UserId,
        expires_at: datetime,
        created_at: datetime | None = None,
        last_seen_at: datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        revoked_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.expires_at = expires_at
        self.created_at = created_at or datetime.now(UTC)
        self.last_seen_at = last_seen_at or self.created_at
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.revoked_at = revoked_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at

    def is_active(self, *, now: datetime | None = None) -> bool:
        return not self.is_revoked and not self.is_expired(now=now)

    def touch(self, *, now: datetime | None = None) -> None:
        self.last_seen_at = now or datetime.now(UTC)

    def revoke(self, *, now: datetime | None = None) -> None:
        self.revoked_at = now or datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Session) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class RefreshToken:
    """Nunca se persiste el valor crudo del token, solo `token_hash`
    (mismo principio que un password: si la base se filtra, no debe
    filtrar tokens usables) — el hashing lo hace `TokenService`
    (infraestructura), esta entidad es agnóstica al algoritmo.

    `rotated_to` implementa Token Rotation: al usarse para refrescar, se
    marca hacia el id del nuevo token y queda inutilizable. Si alguien
    vuelve a presentar un token con `rotated_to` ya seteado, es la señal
    de "refresh token reuse" — evidencia de robo — y dispara
    `RefreshTokenReusedError`, que el caso de uso traduce en revocar toda
    la sesión.
    """

    def __init__(
        self,
        id: RefreshTokenId,
        user_id: UserId,
        session_id: SessionId,
        token_hash: str,
        expires_at: datetime,
        created_at: datetime | None = None,
        revoked_at: datetime | None = None,
        rotated_to: RefreshTokenId | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.session_id = session_id
        self.token_hash = token_hash
        self.expires_at = expires_at
        self.created_at = created_at or datetime.now(UTC)
        self.revoked_at = revoked_at
        self.rotated_to = rotated_to

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_rotated(self) -> bool:
        return self.rotated_to is not None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at

    def is_usable(self, *, now: datetime | None = None) -> bool:
        return not self.is_revoked and not self.is_rotated and not self.is_expired(now=now)

    def rotate(self, new_token_id: RefreshTokenId, *, now: datetime | None = None) -> None:
        if self.is_rotated:
            raise RefreshTokenReusedError(
                f"El refresh token {self.id} ya había sido rotado a {self.rotated_to}: "
                "posible robo/reuso."
            )
        if self.is_revoked or self.is_expired(now=now):
            raise RefreshTokenReusedError(
                f"El refresh token {self.id} no es utilizable (revocado o expirado)."
            )
        self.rotated_to = new_token_id

    def revoke(self, *, now: datetime | None = None) -> None:
        self.revoked_at = now or datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RefreshToken) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class User:
    """Aggregate Root del módulo de identidad."""

    def __init__(
        self,
        id: UserId,
        email: Email,
        username: Username,
        is_active: bool = True,
        is_verified: bool = False,
        role_ids: set[RoleId] | None = None,
        profile: Profile | None = None,
        settings: UserSettings | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.email = email
        self.username = username
        self.is_active = is_active
        self.is_verified = is_verified
        self.role_ids = set(role_ids or set())
        self.profile = profile or Profile()
        self.settings = settings or UserSettings()
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or self.created_at

    def assign_role(self, role_id: RoleId) -> None:
        self.role_ids.add(role_id)
        self._touch()

    def revoke_role(self, role_id: RoleId) -> None:
        self.role_ids.discard(role_id)
        self._touch()

    def update_profile(self, profile: Profile) -> None:
        self.profile = profile
        self._touch()

    def update_settings(self, settings: UserSettings) -> None:
        self.settings = settings
        self._touch()

    def activate(self) -> None:
        self.is_active = True
        self._touch()

    def deactivate(self) -> None:
        self.is_active = False
        self._touch()

    def verify(self) -> None:
        self.is_verified = True
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


__all__ = ["Credential", "Permission", "RefreshToken", "Role", "Session", "User"]
