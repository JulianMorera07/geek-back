from geekbaku.application.providers.stats import StatsTracker
from geekbaku.domain.providers.value_objects import ProviderId

PROVIDER_A = ProviderId("provider-a")


class TestProviderStats:
    def test_starts_at_zero(self) -> None:
        tracker = StatsTracker()
        stats = tracker.get(PROVIDER_A)

        assert stats.total_calls == 0
        assert stats.average_response_time_ms == 0.0
        assert stats.success_rate == 0.0

    def test_records_success(self) -> None:
        tracker = StatsTracker()

        tracker.record_success(PROVIDER_A, elapsed_ms=100.0)
        tracker.record_success(PROVIDER_A, elapsed_ms=200.0)

        stats = tracker.get(PROVIDER_A)
        assert stats.total_calls == 2
        assert stats.successful_calls == 2
        assert stats.average_response_time_ms == 150.0
        assert stats.success_rate == 1.0
        assert stats.last_call_at is not None

    def test_records_failure(self) -> None:
        tracker = StatsTracker()

        tracker.record_success(PROVIDER_A, elapsed_ms=100.0)
        tracker.record_failure(PROVIDER_A, "boom")

        stats = tracker.get(PROVIDER_A)
        assert stats.total_calls == 2
        assert stats.failed_calls == 1
        assert stats.last_error == "boom"
        assert stats.success_rate == 0.5

    def test_records_retries_rate_limits_and_circuit_rejections(self) -> None:
        tracker = StatsTracker()

        tracker.record_retry(PROVIDER_A)
        tracker.record_retry(PROVIDER_A)
        tracker.record_rate_limited(PROVIDER_A)
        tracker.record_circuit_rejected(PROVIDER_A)

        stats = tracker.get(PROVIDER_A)
        assert stats.retried_calls == 2
        assert stats.rate_limited_calls == 1
        assert stats.circuit_rejected_calls == 1
        # ninguno de estos cuenta como "total_calls" (no llegó a intentarse)
        assert stats.total_calls == 0

    def test_records_cache_hits_and_misses(self) -> None:
        tracker = StatsTracker()

        tracker.record_cache_hit(PROVIDER_A)
        tracker.record_cache_hit(PROVIDER_A)
        tracker.record_cache_miss(PROVIDER_A)

        stats = tracker.get(PROVIDER_A)
        assert stats.cache_hits == 2
        assert stats.cache_misses == 1

    def test_records_fallback_used(self) -> None:
        tracker = StatsTracker()
        tracker.record_fallback_used(PROVIDER_A)
        assert tracker.get(PROVIDER_A).fallback_used_calls == 1

    def test_get_all_returns_every_tracked_provider(self) -> None:
        tracker = StatsTracker()
        tracker.record_success(PROVIDER_A, elapsed_ms=1.0)
        tracker.record_success(ProviderId("provider-b"), elapsed_ms=1.0)

        all_stats = tracker.get_all()

        assert set(all_stats.keys()) == {PROVIDER_A, ProviderId("provider-b")}

    def test_providers_tracked_independently(self) -> None:
        tracker = StatsTracker()
        tracker.record_success(PROVIDER_A, elapsed_ms=1.0)

        assert tracker.get(ProviderId("provider-b")).total_calls == 0
