"""Sistema de estadísticas por provider.

`ProviderManager` actualiza un `ProviderStats` por provider en cada etapa
del despacho (`_dispatch`): éxito, falla, reintento, rate-limit, circuit
breaker, cache hit/miss. Es información puramente observacional (no
modifica el comportamiento del Manager, a diferencia de `HealthTracker` o
`CircuitBreaker`) — pensada para una futura vista de administración/monitoreo.
"""

from __future__ import annotations

from datetime import UTC, datetime

from geekbaku.domain.providers.value_objects import ProviderId


class ProviderStats:
    """Contadores acumulados para un provider. Mutable: `StatsTracker` la
    actualiza in-place en cada llamada.
    """

    def __init__(self, provider_id: ProviderId) -> None:
        self.provider_id = provider_id
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.retried_calls = 0
        self.rate_limited_calls = 0
        self.circuit_rejected_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.fallback_used_calls = 0
        self._total_response_time_ms = 0.0
        self.last_call_at: datetime | None = None
        self.last_error: str | None = None

    @property
    def average_response_time_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self._total_response_time_ms / self.successful_calls

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    def _record_call(self) -> None:
        self.total_calls += 1
        self.last_call_at = datetime.now(UTC)

    def record_success(self, elapsed_ms: float) -> None:
        self._record_call()
        self.successful_calls += 1
        self._total_response_time_ms += elapsed_ms
        self.last_error = None

    def record_failure(self, error: str) -> None:
        self._record_call()
        self.failed_calls += 1
        self.last_error = error

    def record_retry(self) -> None:
        self.retried_calls += 1

    def record_rate_limited(self) -> None:
        self.rate_limited_calls += 1

    def record_circuit_rejected(self) -> None:
        self.circuit_rejected_calls += 1

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def record_fallback_used(self) -> None:
        self.fallback_used_calls += 1


class StatsTracker:
    """Mantiene un `ProviderStats` por provider, creándolo bajo demanda."""

    def __init__(self) -> None:
        self._stats: dict[ProviderId, ProviderStats] = {}

    def get(self, provider_id: ProviderId) -> ProviderStats:
        if provider_id not in self._stats:
            self._stats[provider_id] = ProviderStats(provider_id)
        return self._stats[provider_id]

    def get_all(self) -> dict[ProviderId, ProviderStats]:
        return dict(self._stats)

    def record_success(self, provider_id: ProviderId, elapsed_ms: float) -> None:
        self.get(provider_id).record_success(elapsed_ms)

    def record_failure(self, provider_id: ProviderId, error: str) -> None:
        self.get(provider_id).record_failure(error)

    def record_retry(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_retry()

    def record_rate_limited(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_rate_limited()

    def record_circuit_rejected(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_circuit_rejected()

    def record_cache_hit(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_cache_hit()

    def record_cache_miss(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_cache_miss()

    def record_fallback_used(self, provider_id: ProviderId) -> None:
        self.get(provider_id).record_fallback_used()
