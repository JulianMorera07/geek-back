"""Puertos del módulo de identidad.

`AuthenticationProvider` es el puerto central de la arquitectura pedida en
el Sprint 9: cada estrategia de autenticación (password hoy; OAuth/OIDC/
magic-link en un sprint futuro) implementa este Protocol sin que el
dominio ni los casos de uso sepan cuál está activa. `LoginUser` no conoce
`PasswordAuthenticationProvider` — conoce `AuthenticationProviderRegistry`
y le pide "el provider 'password'" por nombre.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from geekbaku.domain.identity.entities import (
    Credential,
    Permission,
    RefreshToken,
    Role,
    Session,
    User,
)
from geekbaku.domain.identity.value_objects import (
    Identity,
    PermissionId,
    RefreshTokenId,
    RoleId,
    SessionId,
    UserId,
)


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UserId) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_username(self, username: str) -> User | None: ...
    async def add(self, user: User) -> None: ...
    async def update(self, user: User) -> None: ...


class RoleRepository(Protocol):
    async def get_by_id(self, role_id: RoleId) -> Role | None: ...
    async def get_by_name(self, name: str) -> Role | None: ...
    async def list_by_ids(self, role_ids: Iterable[RoleId]) -> list[Role]: ...
    async def add(self, role: Role) -> None: ...


class PermissionRepository(Protocol):
    async def get_by_id(self, permission_id: PermissionId) -> Permission | None: ...
    async def list_by_ids(self, permission_ids: Iterable[PermissionId]) -> list[Permission]: ...
    async def add(self, permission: Permission) -> None: ...


class CredentialRepository(Protocol):
    async def get_by_user_and_provider(
        self, user_id: UserId, provider_id: str
    ) -> Credential | None: ...
    async def add(self, credential: Credential) -> None: ...
    async def update(self, credential: Credential) -> None: ...


class SessionRepository(Protocol):
    async def get_by_id(self, session_id: SessionId) -> Session | None: ...
    async def add(self, session: Session) -> None: ...
    async def update(self, session: Session) -> None: ...


class RefreshTokenRepository(Protocol):
    async def get_by_id(self, token_id: RefreshTokenId) -> RefreshToken | None: ...
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def list_by_session(self, session_id: SessionId) -> list[RefreshToken]: ...
    async def add(self, token: RefreshToken) -> None: ...
    async def update(self, token: RefreshToken) -> None: ...


class IdentityUnitOfWork(Protocol):
    """Agrupa los 6 repos de identidad — mismo patrón que
    `application.catalog.ports.CatalogUnitOfWork`.
    """

    users: UserRepository
    roles: RoleRepository
    permissions: PermissionRepository
    credentials: CredentialRepository
    sessions: SessionRepository
    refresh_tokens: RefreshTokenRepository


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...


class AuthenticationProvider(Protocol):
    """Una estrategia de autenticación pluggable."""

    @property
    def provider_id(self) -> str: ...

    async def authenticate(
        self, credentials: Mapping[str, str], uow: IdentityUnitOfWork
    ) -> User: ...


class TokenService(Protocol):
    """Emite y valida `AccessToken`/`RefreshToken`. La implementación
    concreta (JWT hoy) es intercambiable sin tocar ningún caso de uso.
    """

    def issue_access_token(self, identity: Identity) -> tuple[str, int]:
        """Devuelve (token, expires_in_seconds)."""
        ...

    def decode_access_token(self, token: str) -> Identity: ...

    def generate_refresh_token_value(self) -> str: ...

    def hash_refresh_token(self, raw_token: str) -> str: ...

    def refresh_token_ttl_seconds(self) -> int: ...


class BruteForceGuard(Protocol):
    """Protección de fuerza bruta, independiente del `RateLimiter` del
    Provider Framework (Sprint 4) a propósito: Identity no puede depender
    de `application.providers`.
    """

    async def register_failure(self, key: str) -> None: ...

    async def register_success(self, key: str) -> None: ...

    async def is_blocked(self, key: str) -> bool: ...


__all__ = [
    "AuthenticationProvider",
    "BruteForceGuard",
    "CredentialRepository",
    "IdentityUnitOfWork",
    "PasswordHasher",
    "PermissionRepository",
    "RefreshTokenRepository",
    "RoleRepository",
    "SessionRepository",
    "TokenService",
    "UserRepository",
]
