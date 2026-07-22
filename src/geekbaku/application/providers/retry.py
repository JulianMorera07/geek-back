"""Retry Policy: reintentos automáticos con backoff exponencial.

Cada provider define su propia política vía `RetryConfig`
(`ProviderConfiguration.retry`). `RetryPolicy.run` ejecuta una operación
async y, si falla, reintenta hasta `max_attempts` veces, esperando
`backoff_base_seconds * backoff_multiplier ** (intento - 1)` entre cada uno.

La función de espera es inyectable (`sleep`) para que los tests no dependan
de tiempo real.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from geekbaku.domain.providers.value_objects import RetryConfig

OnRetryCallback = Callable[[int, Exception], None]


class RetryPolicy:
    """Ejecuta una operación async con reintentos y backoff exponencial."""

    def __init__(self, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sleep = sleep

    async def run[T](
        self,
        config: RetryConfig,
        operation: Callable[[], Awaitable[T]],
        *,
        on_retry: OnRetryCallback | None = None,
    ) -> T:
        delay = config.backoff_base_seconds
        last_exc: Exception | None = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return await operation()
            except Exception as exc:  # noqa: BLE001 - se reintenta/re-lanza deliberadamente
                last_exc = exc
                if attempt == config.max_attempts:
                    break
                if on_retry is not None:
                    on_retry(attempt, exc)
                await self._sleep(delay)
                delay *= config.backoff_multiplier

        assert last_exc is not None  # invariante: solo se sale del loop tras fallar
        raise last_exc
