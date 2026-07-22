"""Provider Health / Status: lleva el `ProviderHealth` de cada provider.

El `HealthTracker` es la pieza que el `ProviderManager` actualiza después de
cada llamada real. Se usa para decidir el orden/inclusión de providers en
operaciones agregadas (`ProviderManager._fan_out`) — nunca para bloquear una
llamada dirigida a un provider específico (ver `domain/providers/entities.py:ProviderHealth`).
"""

from __future__ import annotations

from geekbaku.domain.providers.entities import ProviderHealth
from geekbaku.domain.providers.value_objects import ProviderId


class HealthTracker:
    """Mantiene un `ProviderHealth` por provider, creándolo bajo demanda."""

    def __init__(self, degraded_after: int = 1, down_after: int = 3) -> None:
        if degraded_after < 1:
            raise ValueError("degraded_after debe ser al menos 1.")
        if down_after < degraded_after:
            raise ValueError("down_after debe ser >= degraded_after.")
        self._health: dict[ProviderId, ProviderHealth] = {}
        self._degraded_after = degraded_after
        self._down_after = down_after

    def get(self, provider_id: ProviderId) -> ProviderHealth:
        if provider_id not in self._health:
            self._health[provider_id] = ProviderHealth(provider_id)
        return self._health[provider_id]

    def record_success(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_success()

    def record_failure(self, provider_id: ProviderId, error: str) -> None:
        self.get(provider_id).record_failure(
            error, degraded_after=self._degraded_after, down_after=self._down_after
        )

    def is_available(self, provider_id: ProviderId) -> bool:
        return self.get(provider_id).is_available()
