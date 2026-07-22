"""Test doubles del módulo de identidad. `InMemoryIdentityUnitOfWork` (la
implementación real, ver `infrastructure.identity.repositories`) se
reutiliza directamente en los tests de casos de uso — mismo criterio que
`InMemoryPlaybackSessionRepository` en el Sprint 7 — así que acá solo hace
falta doblar `PasswordHasher`, `TokenService` y `BruteForceGuard`.
"""

from __future__ import annotations

from geekbaku.domain.identity.exceptions import AuthenticationError
from geekbaku.domain.identity.value_objects import Identity


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


class FakeTokenService:
    def __init__(self, refresh_ttl_seconds: int = 3600) -> None:
        self._issued: dict[str, Identity] = {}
        self._counter = 0
        self._refresh_ttl = refresh_ttl_seconds

    def issue_access_token(self, identity: Identity) -> tuple[str, int]:
        self._counter += 1
        token = f"access-{self._counter}"
        self._issued[token] = identity
        return token, 900

    def decode_access_token(self, token: str) -> Identity:
        try:
            return self._issued[token]
        except KeyError as exc:
            raise AuthenticationError("Access token inválido.") from exc

    def generate_refresh_token_value(self) -> str:
        self._counter += 1
        return f"refresh-{self._counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        return f"hash:{raw_token}"

    def refresh_token_ttl_seconds(self) -> int:
        return self._refresh_ttl


class FakeBruteForceGuard:
    def __init__(self, *, blocked_keys: set[str] | None = None) -> None:
        self.blocked_keys = blocked_keys or set()
        self.failures: dict[str, int] = {}
        self.successes: list[str] = []

    async def register_failure(self, key: str) -> None:
        self.failures[key] = self.failures.get(key, 0) + 1

    async def register_success(self, key: str) -> None:
        self.successes.append(key)

    async def is_blocked(self, key: str) -> bool:
        return key in self.blocked_keys
