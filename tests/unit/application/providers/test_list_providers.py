from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.use_cases.list_providers import ListProviders
from geekbaku.domain.providers.value_objects import ProviderId, ProviderStatus
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_A = ProviderId("provider-a")


class TestListProviders:
    async def test_returns_empty_list_when_no_providers_registered(self) -> None:
        manager = ProviderManager()

        result = await ListProviders(manager).execute()

        assert result == []

    async def test_returns_registered_provider_info(self) -> None:
        manager = ProviderManager()
        manager.register(PROVIDER_A, FakeProviderPort(genres=["Action"]), priority=5)

        result = await ListProviders(manager).execute()

        assert len(result) == 1
        info = result[0]
        assert info.provider_id == "provider-a"
        assert info.priority == 5
        assert info.is_enabled is True
        assert info.health_status == str(ProviderStatus.UNKNOWN)
        assert info.total_calls == 0

    async def test_reflects_health_and_stats_after_a_call(self) -> None:
        manager = ProviderManager()
        manager.register(PROVIDER_A, FakeProviderPort(genres=["Action"]))
        await manager.get_genres(PROVIDER_A)

        result = await ListProviders(manager).execute()

        info = result[0]
        assert info.health_status == str(ProviderStatus.HEALTHY)
        assert info.total_calls == 1
        assert info.successful_calls == 1
