"""Cache de consultas a providers, configurable por `CacheConfig`
(`ProviderConfiguration.cache`: habilitada o no, TTL).

`ProviderCache` es el puerto; `InMemoryProviderCache` es la implementación
de referencia (sin dependencias externas) que usa el `ProviderManager` por
default. Un adapter distribuido (Redis, reutilizando
`infrastructure/cache/redis_client.py`) puede reemplazarla sin tocar el
Manager — queda para un sprint futuro cuando haga falta compartir cache
entre múltiples instancias del backend.

Solo se cachea información que NO es específica de un usuario (detalle,
episodios, temporadas, relacionados, géneros, tipos, resultados de
búsqueda/últimos/populares): nada de `WatchProgress` ni cualquier dato de
reproducción por-usuario pasa por acá.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol


class ProviderCache(Protocol):
    """Cache genérico de valores por clave, con expiración por TTL."""

    async def get(self, key: str) -> object | None: ...

    async def set(self, key: str, value: object, ttl_seconds: float) -> None: ...

    async def invalidate(self, key: str) -> None: ...

    async def invalidate_matching(self, predicate: Callable[[str], bool]) -> None: ...


class InMemoryProviderCache:
    """Cache in-memory de un solo proceso. No apta para múltiples réplicas
    del backend (cada una tendría su propia caché) — suficiente mientras no
    haya un adapter distribuido real.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._store: dict[str, tuple[float, object]] = {}

    async def get(self, key: str) -> object | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return None

        return value

    async def set(self, key: str, value: object, ttl_seconds: float) -> None:
        self._store[key] = (self._clock() + ttl_seconds, value)

    async def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    async def invalidate_matching(self, predicate: Callable[[str], bool]) -> None:
        for key in [k for k in self._store if predicate(k)]:
            del self._store[key]

    def clear(self) -> None:
        self._store.clear()


def build_cache_key(operation: str, *parts: str) -> str:
    """Construye una clave de cache determinística a partir de la operación
    y sus argumentos relevantes (ej. provider_id, query, página).
    """
    return ":".join((operation, *parts))
