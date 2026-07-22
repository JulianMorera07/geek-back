from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.aggregation.use_cases.get_aggregated_detail import (
    GetAggregatedAnimeDetail,
)
from geekbaku.application.aggregation.use_cases.search_aggregated_anime import (
    SearchAggregatedAnime,
)
from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_A = ProviderId("provider-a")


class TestSearchAggregatedAnime:
    async def test_returns_merged_results(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await SearchAggregatedAnime(engine).execute("naruto")

        assert len(results) == 1
        assert results[0].title == "Naruto"

    async def test_restricts_to_given_provider_ids(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await SearchAggregatedAnime(engine).execute(
            "naruto", provider_ids=("provider-a",)
        )

        assert len(results) == 1


class TestGetAggregatedAnimeDetail:
    async def test_merges_detail(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                anime_detail=ProviderAnimeDTO(
                    reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
                    title="Naruto",
                )
            ),
        )
        engine = AggregationEngine(manager=manager)

        result = await GetAggregatedAnimeDetail(engine).execute(
            (ExternalReferenceDTO(provider_id="provider-a", external_id="1"),)
        )

        assert result is not None
        assert result.title == "Naruto"

    async def test_returns_none_for_empty_references(self) -> None:
        manager = ProviderManager()
        engine = AggregationEngine(manager=manager)

        result = await GetAggregatedAnimeDetail(engine).execute(())

        assert result is None
