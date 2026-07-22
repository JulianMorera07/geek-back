"""Rate Limiting: cada provider define su propio límite vía `RateLimitConfig`
(`ProviderConfiguration.rate_limit`). Implementación de ventana fija: cuenta
peticiones dentro de una ventana de `period_seconds`; al agotarse el cupo,
rechaza hasta que la ventana expira y se reinicia el contador.

El reloj es inyectable (`clock: Callable[[], float]`) para que los tests
controlen el paso del tiempo sin `sleep`s reales.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from geekbaku.domain.providers.value_objects import ProviderId, RateLimitConfig


class RateLimiter:
    """Limitador de tasa de ventana fija, con un contador independiente por provider."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[ProviderId, tuple[float, int]] = {}

    def allow(self, provider_id: ProviderId, config: RateLimitConfig | None) -> bool:
        """Devuelve `True` si la petición puede hacerse ahora mismo.

        Sin `config` (provider sin límite configurado), siempre permite.
        """
        if config is None:
            return True

        now = self._clock()
        window_start, count = self._windows.get(provider_id, (now, 0))

        if now - window_start >= config.period_seconds:
            window_start, count = now, 0

        if count >= config.max_requests:
            self._windows[provider_id] = (window_start, count)
            return False

        self._windows[provider_id] = (window_start, count + 1)
        return True

    def reset(self, provider_id: ProviderId) -> None:
        self._windows.pop(provider_id, None)
