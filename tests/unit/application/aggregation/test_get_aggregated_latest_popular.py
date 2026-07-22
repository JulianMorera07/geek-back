from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.aggregation.use_cases.get_aggregated_latest import GetAggregatedLatest
from geekbaku.application.aggregation.use_cases.get_aggregated_popular import (
    GetAggregatedPopular,
)
from geekbaku.application.providers.dto import SearchResultDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_A = ProviderId("provider-a")


class TestGetAggregatedLatest:
    async def test_returns_merged_results(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                latest=[SearchResultDTO(provider_id="provider-a", external_id="1", title="Frieren")]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await GetAggregatedLatest(engine).execute()

        assert len(results) == 1
        assert results[0].title == "Frieren"

    async def test_restricts_to_given_provider_ids(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                latest=[SearchResultDTO(provider_id="provider-a", external_id="1", title="Frieren")]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await GetAggregatedLatest(engine).execute(provider_ids=("provider-a",))

        assert len(results) == 1


class TestGetAggregatedPopular:
    async def test_returns_merged_results(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                popular=[
                    SearchResultDTO(provider_id="provider-a", external_id="1", title="Frieren")
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await GetAggregatedPopular(engine).execute()

        assert len(results) == 1
        assert results[0].title == "Frieren"
