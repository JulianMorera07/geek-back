"""`IdentityUnitOfWork` in-memory: implementación real por defecto (no un
doble de test), mismo criterio que
`application.playback.session_store.InMemoryPlaybackSessionRepository`
(Sprint 7): las sesiones/usuarios de un proceso sin base de datos real
todavía son un default de producción razonable hoy, no un stopgap.

Siembra los roles/permisos base ('user'/'admin') al construirse, para que
`RegisterUser` siempre encuentre el rol por defecto sin necesitar un paso
de "seed" separado — igual que `ProviderRegistry` empieza vacío pero acá
sí conviene arrancar con RBAC mínimo utilizable.
"""

from __future__ import annotations

from collections.abc import Iterable

from geekbaku.application.identity.ports import (
    CredentialRepository,
    PermissionRepository,
    RefreshTokenRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from geekbaku.domain.identity.entities import (
    Credential,
    Permission,
    RefreshToken,
    Role,
    Session,
    User,
)
from geekbaku.domain.identity.value_objects import (
    CredentialId,
    PermissionId,
    RefreshTokenId,
    RoleId,
    SessionId,
    UserId,
)

#: Permisos base: (resource, action, description).
_BASELINE_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("profile", "read", "Ver el propio perfil."),
    ("profile", "update", "Editar el propio perfil/settings."),
    ("catalog", "read", "Ver el catálogo público."),
    ("admin", "manage", "Administrar usuarios, roles y permisos."),
)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[UserId, User] = {}

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        for user in self._by_id.values():
            if str(user.email) == normalized:
                return user
        return None

    async def get_by_username(self, username: str) -> User | None:
        for user in self._by_id.values():
            if str(user.username) == username:
                return user
        return None

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def update(self, user: User) -> None:
        self._by_id[user.id] = user


class InMemoryRoleRepository:
    def __init__(self) -> None:
        self._by_id: dict[RoleId, Role] = {}

    async def get_by_id(self, role_id: RoleId) -> Role | None:
        return self._by_id.get(role_id)

    async def get_by_name(self, name: str) -> Role | None:
        for role in self._by_id.values():
            if role.name == name:
                return role
        return None

    async def list_by_ids(self, role_ids: Iterable[RoleId]) -> list[Role]:
        wanted = set(role_ids)
        return [role for role_id, role in self._by_id.items() if role_id in wanted]

    async def add(self, role: Role) -> None:
        self._by_id[role.id] = role

    def add_sync(self, role: Role) -> None:
        """Solo para sembrar datos base en el constructor del UoW, donde no
        hay ningún `await` disponible (ver `InMemoryIdentityUnitOfWork`)."""
        self._by_id[role.id] = role


class InMemoryPermissionRepository:
    def __init__(self) -> None:
        self._by_id: dict[PermissionId, Permission] = {}

    async def get_by_id(self, permission_id: PermissionId) -> Permission | None:
        return self._by_id.get(permission_id)

    async def list_by_ids(self, permission_ids: Iterable[PermissionId]) -> list[Permission]:
        wanted = set(permission_ids)
        return [perm for perm_id, perm in self._by_id.items() if perm_id in wanted]

    async def add(self, permission: Permission) -> None:
        self._by_id[permission.id] = permission

    def add_sync(self, permission: Permission) -> None:
        self._by_id[permission.id] = permission


class InMemoryCredentialRepository:
    def __init__(self) -> None:
        self._by_id: dict[CredentialId, Credential] = {}

    async def get_by_user_and_provider(
        self, user_id: UserId, provider_id: str
    ) -> Credential | None:
        for credential in self._by_id.values():
            if credential.user_id == user_id and credential.provider_id == provider_id:
                return credential
        return None

    async def add(self, credential: Credential) -> None:
        self._by_id[credential.id] = credential

    async def update(self, credential: Credential) -> None:
        self._by_id[credential.id] = credential


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[SessionId, Session] = {}

    async def get_by_id(self, session_id: SessionId) -> Session | None:
        return self._by_id.get(session_id)

    async def add(self, session: Session) -> None:
        self._by_id[session.id] = session

    async def update(self, session: Session) -> None:
        self._by_id[session.id] = session


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self._by_id: dict[RefreshTokenId, RefreshToken] = {}

    async def get_by_id(self, token_id: RefreshTokenId) -> RefreshToken | None:
        return self._by_id.get(token_id)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._by_id.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def list_by_session(self, session_id: SessionId) -> list[RefreshToken]:
        return [token for token in self._by_id.values() if token.session_id == session_id]

    async def add(self, token: RefreshToken) -> None:
        self._by_id[token.id] = token

    async def update(self, token: RefreshToken) -> None:
        self._by_id[token.id] = token


class InMemoryIdentityUnitOfWork:
    """Se siembra a sí mismo con los roles/permisos base en el
    constructor (síncrono): no hay I/O real detrás de estos repos, así
    que sembrar acá evita depender de un hook de startup async solo para
    poblar datos en memoria.

    Los atributos públicos se anotan con el tipo `Protocol`
    (`application.identity.ports`), no con la clase concreta: mypy exige
    invariancia en atributos de instancia para que `InMemoryIdentityUnitOfWork`
    sea aceptado donde se pide un `IdentityUnitOfWork`.
    """

    def __init__(self) -> None:
        users = InMemoryUserRepository()
        roles = InMemoryRoleRepository()
        permissions = InMemoryPermissionRepository()
        credentials = InMemoryCredentialRepository()
        sessions = InMemorySessionRepository()
        refresh_tokens = InMemoryRefreshTokenRepository()

        self._seed_default_roles(roles, permissions)

        self.users: UserRepository = users
        self.roles: RoleRepository = roles
        self.permissions: PermissionRepository = permissions
        self.credentials: CredentialRepository = credentials
        self.sessions: SessionRepository = sessions
        self.refresh_tokens: RefreshTokenRepository = refresh_tokens

    @staticmethod
    def _seed_default_roles(
        roles: InMemoryRoleRepository, permissions: InMemoryPermissionRepository
    ) -> None:
        permissions_by_key: dict[str, Permission] = {}
        for resource, action, description in _BASELINE_PERMISSIONS:
            permission = Permission(
                id=PermissionId.new(), resource=resource, action=action, description=description
            )
            permissions.add_sync(permission)
            permissions_by_key[permission.key] = permission

        user_role = Role(
            id=RoleId.new(),
            name="user",
            permission_ids={
                permissions_by_key["profile:read"].id,
                permissions_by_key["profile:update"].id,
                permissions_by_key["catalog:read"].id,
            },
            is_system=True,
        )
        roles.add_sync(user_role)

        admin_role = Role(
            id=RoleId.new(),
            name="admin",
            permission_ids={p.id for p in permissions_by_key.values()},
            is_system=True,
        )
        roles.add_sync(admin_role)


__all__ = ["InMemoryIdentityUnitOfWork"]
