from geekbaku.domain.providers.entities import ProviderHealth, StreamingProvider
from geekbaku.domain.providers.value_objects import ProviderId, ProviderMetadata, ProviderStatus


def make_provider(enabled: bool = True) -> StreamingProvider:
    return StreamingProvider(
        id=ProviderId("provider-a"),
        metadata=ProviderMetadata(display_name="Provider A"),
        is_enabled=enabled,
    )


class TestStreamingProvider:
    def test_enable_and_disable(self) -> None:
        provider = make_provider(enabled=False)
        assert provider.is_enabled is False

        provider.enable()
        assert provider.is_enabled is True

        provider.disable()
        assert provider.is_enabled is False

    def test_equality_by_id(self) -> None:
        provider_id = ProviderId("provider-a")
        provider_a = StreamingProvider(
            id=provider_id, metadata=ProviderMetadata(display_name="A")
        )
        provider_b = StreamingProvider(
            id=provider_id, metadata=ProviderMetadata(display_name="Different")
        )
        assert provider_a == provider_b
        assert hash(provider_a) == hash(provider_b)


class TestProviderHealth:
    def test_starts_unknown(self) -> None:
        health = ProviderHealth(ProviderId("provider-a"))
        assert health.status == ProviderStatus.UNKNOWN
        assert health.is_available() is True

    def test_record_success_marks_healthy(self) -> None:
        health = ProviderHealth(ProviderId("provider-a"))
        health.record_failure("boom")

        health.record_success()

        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.last_error is None
        assert health.last_success_at is not None

    def test_first_failure_marks_degraded(self) -> None:
        health = ProviderHealth(ProviderId("provider-a"))

        health.record_failure("timeout")

        assert health.status == ProviderStatus.DEGRADED
        assert health.consecutive_failures == 1
        assert health.last_error == "timeout"
        assert health.is_available() is True

    def test_reaches_down_after_threshold(self) -> None:
        health = ProviderHealth(ProviderId("provider-a"))

        for _ in range(3):
            health.record_failure("timeout", down_after=3)

        assert health.status == ProviderStatus.DOWN
        assert health.is_available() is False

    def test_success_resets_failure_streak(self) -> None:
        health = ProviderHealth(ProviderId("provider-a"))
        health.record_failure("timeout", down_after=3)
        health.record_failure("timeout", down_after=3)

        health.record_success()
        health.record_failure("timeout", down_after=3)

        assert health.status == ProviderStatus.DEGRADED
        assert health.consecutive_failures == 1

    def test_equality_by_provider_id(self) -> None:
        provider_id = ProviderId("provider-a")
        health_a = ProviderHealth(provider_id)
        health_b = ProviderHealth(provider_id)
        assert health_a == health_b
        assert hash(health_a) == hash(health_b)
