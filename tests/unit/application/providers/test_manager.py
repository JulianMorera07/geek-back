import logging

import pytest

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import InMemoryProviderCache
from geekbaku.application.providers.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from geekbaku.application.providers.dto import SearchResultDTO
from geekbaku.application.providers.exceptions import ProviderCircuitOpenError
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.registry import ProviderRegistry
from geekbaku.application.providers.retry import RetryPolicy
from geekbaku.domain.providers.exceptions import (
    ProviderNotFoundError,
    ProviderRateLimitExceededError,
    ProviderRequestError,
)
from geekbaku.domain.providers.value_objects import (
    CacheConfig,
    ProviderConfiguration,
    ProviderId,
    ProviderStatus,
    RateLimitConfig,
    RetryConfig,
)
from tests.unit.application.providers.fakes import (
    FailingProviderPort,
    FakeProviderPort,
    FlakyProviderPort,
    SlowProviderPort,
)

PROVIDER_A = ProviderId("provider-a")
PROVIDER_B = ProviderId("provider-b")


async def _no_sleep(_seconds: float) -> None:
    return None


def make_manager(**kwargs: object) -> ProviderManager:
    kwargs.setdefault("retry_policy", RetryPolicy(sleep=_no_sleep))
    return ProviderManager(**kwargs)  # type: ignore[arg-type]


class TestRegistrationCompat:
    """El API de registro se mantiene compatible con el `ProviderEngine` del
    Sprint 3 (`register(provider_id, adapter)`), ahora delegando en `ProviderRegistry`.
    """

    def test_register_and_get(self) -> None:
        manager = make_manager()
        adapter = FakeProviderPort()
        manager.register(PROVIDER_A, adapter)

        assert manager.get(PROVIDER_A) is adapter
        assert manager.list_provider_ids() == (PROVIDER_A,)

    def test_unregister(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FakeProviderPort())
        manager.unregister(PROVIDER_A)
        assert manager.list_provider_ids() == ()

    def test_get_unknown_raises(self) -> None:
        manager = make_manager()
        with pytest.raises(ProviderNotFoundError):
            manager.get(PROVIDER_A)


class TestHealthTracking:
    async def test_success_marks_healthy(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FakeProviderPort(genres=["Action"]))

        await manager.get_genres(PROVIDER_A)

        health = manager.get_health(PROVIDER_A)
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0

    async def test_failures_mark_down_after_threshold(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FailingProviderPort())

        for _ in range(3):
            with pytest.raises(ProviderRequestError):
                await manager.get_genres(PROVIDER_A)

        health = manager.get_health(PROVIDER_A)
        assert health.status == ProviderStatus.DOWN
        assert health.consecutive_failures == 3

    def test_unknown_provider_health_defaults_to_unknown(self) -> None:
        manager = make_manager()
        assert manager.get_health(PROVIDER_A).status == ProviderStatus.UNKNOWN


class TestRetry:
    async def test_retries_until_success(self) -> None:
        adapter = FlakyProviderPort(fail_times=2, genres=["Action"])
        registry = ProviderRegistry()
        registry.register(
            PROVIDER_A,
            adapter,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                retry=RetryConfig(max_attempts=3, backoff_base_seconds=0),
            ),
        )
        manager = make_manager(registry=registry)

        genres = await manager.get_genres(PROVIDER_A)

        assert genres == ["Action"]
        assert adapter.attempts == 3

    async def test_exhausts_retries_and_raises(self) -> None:
        adapter = FlakyProviderPort(fail_times=5, genres=["Action"])
        registry = ProviderRegistry()
        registry.register(
            PROVIDER_A,
            adapter,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                retry=RetryConfig(max_attempts=2, backoff_base_seconds=0),
            ),
        )
        manager = make_manager(registry=registry)

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)

        assert adapter.attempts == 2


class TestRateLimiting:
    async def test_blocks_when_limit_exceeded(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(
            PROVIDER_A,
            adapter,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                rate_limit=RateLimitConfig(max_requests=1, period_seconds=60),
            ),
        )
        manager = make_manager(registry=registry)

        await manager.get_genres(PROVIDER_A)
        with pytest.raises(ProviderRateLimitExceededError):
            await manager.get_genres(PROVIDER_A)

        assert adapter.call_count["get_genres"] == 1


class TestCache:
    async def test_cache_hit_avoids_second_call(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(
            PROVIDER_A,
            adapter,
            configuration=ProviderConfiguration(provider_id=PROVIDER_A, base_url="https://x"),
        )
        manager = make_manager(registry=registry, cache=InMemoryProviderCache())

        first = await manager.get_genres(PROVIDER_A)
        second = await manager.get_genres(PROVIDER_A)

        assert first == second == ["Action"]
        assert adapter.call_count["get_genres"] == 1

    async def test_cache_disabled_per_provider(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(
            PROVIDER_A,
            adapter,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A, base_url="https://x", cache=CacheConfig(enabled=False)
            ),
        )
        manager = make_manager(registry=registry, cache=InMemoryProviderCache())

        await manager.get_genres(PROVIDER_A)
        await manager.get_genres(PROVIDER_A)

        assert adapter.call_count["get_genres"] == 2

    async def test_without_cache_instance_always_calls_adapter(self) -> None:
        manager = make_manager()  # sin cache
        adapter = FakeProviderPort(genres=["Action"])
        manager.register(PROVIDER_A, adapter)

        await manager.get_genres(PROVIDER_A)
        await manager.get_genres(PROVIDER_A)

        assert adapter.call_count["get_genres"] == 2


class TestFanOutPriority:
    async def test_orders_by_priority_when_no_explicit_providers(self) -> None:
        manager = make_manager()
        low = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-low", external_id="1", title="Low")
            ]
        )
        high = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-high", external_id="2", title="High")
            ]
        )
        manager.register(ProviderId("provider-low"), low, priority=0)
        manager.register(ProviderId("provider-high"), high, priority=10)

        results = await manager.search("naruto", Pagination())

        assert [r.provider_id for r in results] == ["provider-high", "provider-low"]

    async def test_skips_down_providers_in_fan_out(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FailingProviderPort())
        manager.register(
            PROVIDER_B,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(provider_id="provider-b", external_id="1", title="B")
                ]
            ),
        )

        for _ in range(3):
            with pytest.raises(ProviderRequestError):
                await manager.get_genres(PROVIDER_A)
        assert manager.get_health(PROVIDER_A).status == ProviderStatus.DOWN

        results = await manager.search("naruto", Pagination())

        assert [r.provider_id for r in results] == ["provider-b"]

    async def test_disabled_providers_excluded_from_fan_out(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(
            search_results=[SearchResultDTO(provider_id="provider-a", external_id="1", title="A")]
        )
        registry.register(PROVIDER_A, adapter, is_enabled=False)
        manager = make_manager(registry=registry)

        results = await manager.search("naruto", Pagination())

        assert results == []

    async def test_explicit_provider_ids_are_used_as_given(self) -> None:
        manager = make_manager()
        adapter = FakeProviderPort(
            search_results=[SearchResultDTO(provider_id="provider-a", external_id="1", title="A")]
        )
        manager.register(PROVIDER_A, adapter)

        results = await manager.search("naruto", Pagination(), provider_ids=(PROVIDER_A,))

        assert len(results) == 1


class TestLogging:
    async def test_logs_success_failure_and_retry(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="geekbaku.providers")

        registry = ProviderRegistry()
        flaky = FlakyProviderPort(fail_times=1, genres=["Action"])
        registry.register(
            PROVIDER_A,
            flaky,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://x",
                retry=RetryConfig(max_attempts=3, backoff_base_seconds=0),
            ),
        )
        manager = make_manager(registry=registry)

        await manager.get_genres(PROVIDER_A)

        messages = [record.getMessage() for record in caplog.records]
        assert any("provider_retry" in m and "provider-a" in m for m in messages)
        assert any("provider_call_succeeded" in m and "provider-a" in m for m in messages)

    async def test_logs_final_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="geekbaku.providers")
        manager = make_manager()
        manager.register(PROVIDER_A, FailingProviderPort())

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)

        messages = [record.getMessage() for record in caplog.records]
        assert any("provider_call_failed" in m and "provider-a" in m for m in messages)


class TestTimeout:
    async def test_slow_call_times_out_and_counts_as_failure(self) -> None:
        registry = ProviderRegistry()
        slow = SlowProviderPort(delay_seconds=0.2, genres=["Action"])
        registry.register(
            PROVIDER_A,
            slow,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                timeout_seconds=0.01,
                retry=RetryConfig(max_attempts=1),
            ),
        )
        manager = make_manager(registry=registry)

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)

        assert manager.get_health(PROVIDER_A).consecutive_failures == 1

    async def test_fast_call_within_timeout_succeeds(self) -> None:
        registry = ProviderRegistry()
        fast = SlowProviderPort(delay_seconds=0.0, genres=["Action"])
        registry.register(
            PROVIDER_A,
            fast,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A, base_url="https://example.com", timeout_seconds=5.0
            ),
        )
        manager = make_manager(registry=registry)

        genres = await manager.get_genres(PROVIDER_A)

        assert genres == ["Action"]


class TestCircuitBreakerIntegration:
    async def test_opens_after_threshold_and_stops_calling_adapter(self) -> None:
        breaker = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        manager = make_manager(circuit_breaker=breaker)
        adapter = FailingProviderPort()
        manager.register(PROVIDER_A, adapter)

        for _ in range(2):
            with pytest.raises(ProviderRequestError):
                await manager.get_genres(PROVIDER_A)

        with pytest.raises(ProviderCircuitOpenError):
            await manager.get_genres(PROVIDER_A)

    async def test_half_open_success_closes_circuit(self) -> None:
        clock_value = {"now": 0.0}

        def clock() -> float:
            return clock_value["now"]

        registry = ProviderRegistry()
        flaky = FlakyProviderPort(fail_times=1, genres=["Action"])
        registry.register(
            PROVIDER_A,
            flaky,
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                retry=RetryConfig(max_attempts=1),
            ),
        )
        manager = ProviderManager(
            registry=registry,
            retry_policy=RetryPolicy(sleep=_no_sleep),
            circuit_breaker=CircuitBreaker(
                CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=10), clock=clock
            ),
        )

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)

        clock_value["now"] += 10
        genres = await manager.get_genres(PROVIDER_A)

        assert genres == ["Action"]


class TestFallback:
    async def test_serves_last_known_good_value_on_failure(self) -> None:
        registry = ProviderRegistry()
        # Se registra con un adapter que primero tiene éxito.
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(PROVIDER_A, adapter)
        manager = make_manager(registry=registry)

        first = await manager.get_genres(PROVIDER_A)
        assert first == ["Action"]

        # Reemplaza el adapter registrado por uno que siempre falla, sin tocar
        # el cache de "último valor bueno" que ya guardó el Manager.
        manager.registry.unregister(PROVIDER_A)
        manager.registry.register(PROVIDER_A, FailingProviderPort())

        second = await manager.get_genres(PROVIDER_A)

        assert second == ["Action"]
        assert manager.get_stats(PROVIDER_A).fallback_used_calls == 1

    async def test_raises_when_no_fallback_available(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FailingProviderPort())

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)

    async def test_disabled_fallback_raises_even_with_cached_value(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(PROVIDER_A, adapter)
        manager = ProviderManager(
            registry=registry,
            retry_policy=RetryPolicy(sleep=_no_sleep),
            enable_fallback=False,
        )

        await manager.get_genres(PROVIDER_A)

        registry.unregister(PROVIDER_A)
        registry.register(PROVIDER_A, FailingProviderPort())

        with pytest.raises(ProviderRequestError):
            await manager.get_genres(PROVIDER_A)


class TestDynamicEnableDisable:
    async def test_disable_excludes_from_fan_out(self) -> None:
        manager = make_manager()
        adapter = FakeProviderPort(
            search_results=[SearchResultDTO(provider_id="provider-a", external_id="1", title="A")]
        )
        manager.register(PROVIDER_A, adapter)

        manager.disable(PROVIDER_A)
        results = await manager.search("naruto", Pagination())
        assert results == []

        manager.enable(PROVIDER_A)
        results = await manager.search("naruto", Pagination())
        assert len(results) == 1

    async def test_disabled_provider_still_reachable_via_explicit_id(self) -> None:
        manager = make_manager()
        adapter = FakeProviderPort(
            search_results=[SearchResultDTO(provider_id="provider-a", external_id="1", title="A")]
        )
        manager.register(PROVIDER_A, adapter)
        manager.disable(PROVIDER_A)

        results = await manager.search("naruto", Pagination(), provider_ids=(PROVIDER_A,))

        assert len(results) == 1


class TestStatsIntegration:
    async def test_tracks_success_and_failure_through_manager(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FakeProviderPort(genres=["Action"]))

        await manager.get_genres(PROVIDER_A)

        stats = manager.get_stats(PROVIDER_A)
        assert stats.successful_calls == 1
        assert stats.total_calls == 1

    async def test_tracks_cache_hits(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort(genres=["Action"]))
        manager = make_manager(registry=registry, cache=InMemoryProviderCache())

        await manager.get_genres(PROVIDER_A)
        await manager.get_genres(PROVIDER_A)

        stats = manager.get_stats(PROVIDER_A)
        assert stats.cache_hits == 1
        assert stats.cache_misses == 1

    async def test_tracks_rate_limited_calls(self) -> None:
        registry = ProviderRegistry()
        registry.register(
            PROVIDER_A,
            FakeProviderPort(genres=["Action"]),
            configuration=ProviderConfiguration(
                provider_id=PROVIDER_A,
                base_url="https://example.com",
                rate_limit=RateLimitConfig(max_requests=1, period_seconds=60),
            ),
        )
        manager = make_manager(registry=registry)

        await manager.get_genres(PROVIDER_A)
        with pytest.raises(ProviderRateLimitExceededError):
            await manager.get_genres(PROVIDER_A)

        assert manager.get_stats(PROVIDER_A).rate_limited_calls == 1

    async def test_get_all_stats_returns_every_registered_provider_touched(self) -> None:
        manager = make_manager()
        manager.register(PROVIDER_A, FakeProviderPort(genres=["Action"]))
        manager.register(PROVIDER_B, FakeProviderPort(genres=["Isekai"]))

        await manager.get_genres(PROVIDER_A)
        await manager.get_genres(PROVIDER_B)

        assert set(manager.get_all_stats().keys()) == {PROVIDER_A, PROVIDER_B}


class TestCacheInvalidation:
    async def test_invalidate_cache_forces_fresh_call(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"])
        registry.register(PROVIDER_A, adapter)
        manager = make_manager(registry=registry, cache=InMemoryProviderCache())

        await manager.get_genres(PROVIDER_A)
        await manager.invalidate_cache("get_genres", PROVIDER_A)
        await manager.get_genres(PROVIDER_A)

        assert adapter.call_count["get_genres"] == 2

    async def test_invalidate_provider_cache_clears_all_its_entries(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort(genres=["Action"], types=["TV"])
        registry.register(PROVIDER_A, adapter)
        manager = make_manager(registry=registry, cache=InMemoryProviderCache())

        await manager.get_genres(PROVIDER_A)
        await manager.get_types(PROVIDER_A)
        await manager.invalidate_provider_cache(PROVIDER_A)
        await manager.get_genres(PROVIDER_A)
        await manager.get_types(PROVIDER_A)

        assert adapter.call_count["get_genres"] == 2
        assert adapter.call_count["get_types"] == 2

    async def test_invalidate_cache_without_cache_configured_is_noop(self) -> None:
        manager = make_manager()  # sin cache
        manager.register(PROVIDER_A, FakeProviderPort())
        await manager.invalidate_cache("get_genres", PROVIDER_A)  # no debe lanzar
