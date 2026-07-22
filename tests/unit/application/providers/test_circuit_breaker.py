import pytest

from geekbaku.application.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from geekbaku.domain.providers.value_objects import ProviderId

PROVIDER_A = ProviderId("provider-a")


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class TestCircuitBreakerConfig:
    def test_rejects_non_positive_threshold(self) -> None:
        with pytest.raises(ValueError):
            CircuitBreakerConfig(failure_threshold=0)

    def test_rejects_non_positive_cooldown(self) -> None:
        with pytest.raises(ValueError):
            CircuitBreakerConfig(cooldown_seconds=0)


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        breaker = CircuitBreaker()
        assert breaker.current_state(PROVIDER_A) == CircuitState.CLOSED
        assert breaker.allow_call(PROVIDER_A) is True

    def test_opens_after_threshold_consecutive_failures(self) -> None:
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

        breaker.record_failure(PROVIDER_A)
        breaker.record_failure(PROVIDER_A)
        assert breaker.current_state(PROVIDER_A) == CircuitState.CLOSED

        breaker.record_failure(PROVIDER_A)
        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN
        assert breaker.allow_call(PROVIDER_A) is False

    def test_success_resets_failure_count(self) -> None:
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))

        breaker.record_failure(PROVIDER_A)
        breaker.record_failure(PROVIDER_A)
        breaker.record_success(PROVIDER_A)
        breaker.record_failure(PROVIDER_A)
        breaker.record_failure(PROVIDER_A)

        assert breaker.current_state(PROVIDER_A) == CircuitState.CLOSED

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=30), clock=clock
        )

        breaker.record_failure(PROVIDER_A)
        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN

        clock.now += 29
        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN

        clock.now += 2
        assert breaker.current_state(PROVIDER_A) == CircuitState.HALF_OPEN
        assert breaker.allow_call(PROVIDER_A) is True

    def test_half_open_success_closes_circuit(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=10), clock=clock
        )
        breaker.record_failure(PROVIDER_A)
        clock.now += 10

        assert breaker.current_state(PROVIDER_A) == CircuitState.HALF_OPEN
        breaker.record_success(PROVIDER_A)

        assert breaker.current_state(PROVIDER_A) == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit_and_resets_cooldown(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=10), clock=clock
        )
        breaker.record_failure(PROVIDER_A)
        clock.now += 10
        assert breaker.current_state(PROVIDER_A) == CircuitState.HALF_OPEN

        breaker.record_failure(PROVIDER_A)

        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN
        clock.now += 5
        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN  # cooldown se reinició

    def test_providers_are_independent(self) -> None:
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        breaker.record_failure(PROVIDER_A)

        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN
        assert breaker.current_state(ProviderId("provider-b")) == CircuitState.CLOSED

    def test_reset_clears_state(self) -> None:
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        breaker.record_failure(PROVIDER_A)
        assert breaker.current_state(PROVIDER_A) == CircuitState.OPEN

        breaker.reset(PROVIDER_A)

        assert breaker.current_state(PROVIDER_A) == CircuitState.CLOSED
