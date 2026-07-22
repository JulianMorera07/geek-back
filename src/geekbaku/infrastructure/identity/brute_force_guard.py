"""Brute Force Protection: implementación en memoria de
`application.identity.ports.BruteForceGuard`.

Ventana fija por `key` (típicamente `email:ip`): tras `max_failures`
fallas dentro de `window_seconds`, la key queda bloqueada por el resto de
la ventana. Un login exitoso limpia el contador — igual criterio que
cualquier protección de fuerza bruta estándar (no es una implementación
del `RateLimiter` del Provider Framework, es una nueva, autónoma).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class _Attempts:
    failures: int = 0
    window_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryBruteForceGuard:
    def __init__(self, max_failures: int = 5, window_seconds: int = 900) -> None:
        self._max_failures = max_failures
        self._window = timedelta(seconds=window_seconds)
        self._attempts: dict[str, _Attempts] = {}
        self._lock = asyncio.Lock()

    async def register_failure(self, key: str) -> None:
        async with self._lock:
            entry = self._attempts.get(key)
            now = datetime.now(UTC)
            if entry is None or now - entry.window_started_at >= self._window:
                entry = _Attempts(failures=0, window_started_at=now)
            entry.failures += 1
            self._attempts[key] = entry

    async def register_success(self, key: str) -> None:
        async with self._lock:
            self._attempts.pop(key, None)

    async def is_blocked(self, key: str) -> bool:
        async with self._lock:
            entry = self._attempts.get(key)
            if entry is None:
                return False
            if datetime.now(UTC) - entry.window_started_at >= self._window:
                del self._attempts[key]
                return False
            return entry.failures >= self._max_failures


__all__ = ["InMemoryBruteForceGuard"]
