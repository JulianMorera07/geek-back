"""Circuit Breaker: corta llamadas a un provider que viene fallando en
forma sostenida, en vez de seguir intentando (y pagando el costo de cada
timeout) hasta que se recupere solo.

No es lo mismo que `HealthTracker` (Sprint 4): `HealthTracker` es
observabilidad (para ORDENAR/excluir providers de un fan-out agregado);
`CircuitBreaker` es protección activa (para NO LLAMAR a un provider
específico mientras está `OPEN`), incluso en una llamada dirigida
(`get_anime_detail`, etc.). Ambos se actualizan en paralelo desde
`ProviderManager._dispatch`.

Nota de alcance: esta pieza vive enteramente en `application/`, no en
`domain/`, porque este sprint tiene la restricción explícita de no tocar el
dominio. Es una decisión pragmática, no necesariamente la ubicación
"ideal" a largo plazo — un futuro sprint podría revisitarla junto con
`RateLimitConfig`/`RetryConfig` (que sí viven en `domain/providers`).

Máquina de estados:

    CLOSED --(N fallas consecutivas)--> OPEN
    OPEN --(pasó cooldown_seconds)--> HALF_OPEN
    HALF_OPEN --(1 llamada exitosa)--> CLOSED
    HALF_OPEN --(1 llamada fallida)--> OPEN (cooldown se reinicia)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from geekbaku.domain.providers.value_objects import ProviderId


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold debe ser al menos 1.")
        if self.cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds debe ser mayor a 0.")


class _CircuitBreakerState:
    __slots__ = ("consecutive_failures", "opened_at", "state")

    def __init__(self) -> None:
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.opened_at: float | None = None


class CircuitBreaker:
    """Circuit breaker con un estado independiente por provider."""

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._clock = clock
        self._states: dict[ProviderId, _CircuitBreakerState] = {}

    def _state_for(self, provider_id: ProviderId) -> _CircuitBreakerState:
        if provider_id not in self._states:
            self._states[provider_id] = _CircuitBreakerState()
        return self._states[provider_id]

    def current_state(self, provider_id: ProviderId) -> CircuitState:
        state = self._state_for(provider_id)
        if (
            state.state == CircuitState.OPEN
            and state.opened_at is not None
            and self._clock() - state.opened_at >= self._config.cooldown_seconds
        ):
            state.state = CircuitState.HALF_OPEN
        return state.state

    def allow_call(self, provider_id: ProviderId) -> bool:
        """`False` si el breaker está `OPEN` (todavía dentro del cooldown)."""
        return self.current_state(provider_id) != CircuitState.OPEN

    def record_success(self, provider_id: ProviderId) -> None:
        state = self._state_for(provider_id)
        state.state = CircuitState.CLOSED
        state.consecutive_failures = 0
        state.opened_at = None

    def record_failure(self, provider_id: ProviderId) -> None:
        state = self._state_for(provider_id)

        if state.state == CircuitState.HALF_OPEN:
            state.state = CircuitState.OPEN
            state.opened_at = self._clock()
            return

        state.consecutive_failures += 1
        if state.consecutive_failures >= self._config.failure_threshold:
            state.state = CircuitState.OPEN
            state.opened_at = self._clock()

    def reset(self, provider_id: ProviderId) -> None:
        self._states.pop(provider_id, None)
