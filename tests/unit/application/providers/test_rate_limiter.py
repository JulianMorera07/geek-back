from geekbaku.application.providers.rate_limiter import RateLimiter
from geekbaku.domain.providers.value_objects import ProviderId, RateLimitConfig

PROVIDER_A = ProviderId("provider-a")


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class TestRateLimiter:
    def test_allows_without_config(self) -> None:
        limiter = RateLimiter()
        assert limiter.allow(PROVIDER_A, None) is True
        assert limiter.allow(PROVIDER_A, None) is True

    def test_allows_up_to_max_requests(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(clock=clock)
        config = RateLimitConfig(max_requests=2, period_seconds=60)

        assert limiter.allow(PROVIDER_A, config) is True
        assert limiter.allow(PROVIDER_A, config) is True
        assert limiter.allow(PROVIDER_A, config) is False

    def test_resets_after_period(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(clock=clock)
        config = RateLimitConfig(max_requests=1, period_seconds=60)

        assert limiter.allow(PROVIDER_A, config) is True
        assert limiter.allow(PROVIDER_A, config) is False

        clock.now += 60
        assert limiter.allow(PROVIDER_A, config) is True

    def test_tracks_providers_independently(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(clock=clock)
        config = RateLimitConfig(max_requests=1, period_seconds=60)

        assert limiter.allow(PROVIDER_A, config) is True
        assert limiter.allow(ProviderId("provider-b"), config) is True

    def test_reset_clears_window(self) -> None:
        clock = FakeClock()
        limiter = RateLimiter(clock=clock)
        config = RateLimitConfig(max_requests=1, period_seconds=60)

        limiter.allow(PROVIDER_A, config)
        assert limiter.allow(PROVIDER_A, config) is False

        limiter.reset(PROVIDER_A)
        assert limiter.allow(PROVIDER_A, config) is True
