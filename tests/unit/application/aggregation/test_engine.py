from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import InMemoryProviderCache
from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.providers.fakes import FailingProviderPort, FakeProviderPort

PROVIDER_A = ProviderId("provider-a")
PROVIDER_B = ProviderId("provider-b")


def make_engine(**engine_kwargs: object) -> AggregationEngine:
    manager = ProviderManager()
    return AggregationEngine(manager=manager, **engine_kwargs)  # type: ignore[arg-type]


class TestSearch:
    async def test_deduplicates_results_from_multiple_providers(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(
                        provider_id="provider-a", external_id="1", title="Attack on Titan"
                    )
                ]
            ),
            priority=5,
        )
        manager.register(
            PROVIDER_B,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(
                        provider_id="provider-b",
                        external_id="99",
                        title="Attack on Titan",
                        thumbnail_url="https://cdn.example.com/t.jpg",
                    )
                ]
            ),
            priority=1,
        )
        engine = AggregationEngine(manager=manager)

        results = await engine.search("attack on titan")

        assert len(results) == 1
        assert results[0].thumbnail_url == "https://cdn.example.com/t.jpg"
        assert {s.provider_id for s in results[0].sources} == {"provider-a", "provider-b"}

    async def test_does_not_merge_distinct_anime(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(
                        provider_id="provider-a", external_id="1", title="Attack on Titan"
                    ),
                    SearchResultDTO(provider_id="provider-a", external_id="2", title="One Piece"),
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await engine.search("anime")

        assert len(results) == 2

    async def test_cache_avoids_repeated_provider_calls(self) -> None:
        manager = ProviderManager()
        adapter = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
            ]
        )
        manager.register(PROVIDER_A, adapter)
        engine = AggregationEngine(manager=manager, cache=InMemoryProviderCache())

        await engine.search("naruto")
        await engine.search("naruto")

        assert adapter.call_count["search"] == 1

    async def test_different_queries_are_cached_independently(self) -> None:
        manager = ProviderManager()
        adapter = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
            ]
        )
        manager.register(PROVIDER_A, adapter)
        engine = AggregationEngine(manager=manager, cache=InMemoryProviderCache())

        await engine.search("naruto")
        await engine.search("one piece")

        assert adapter.call_count["search"] == 2

    async def test_invalidate_search_cache_forces_fresh_query(self) -> None:
        manager = ProviderManager()
        adapter = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
            ]
        )
        manager.register(PROVIDER_A, adapter)
        engine = AggregationEngine(manager=manager, cache=InMemoryProviderCache())
        pagination = Pagination()

        await engine.search("naruto", pagination)
        await engine.invalidate_search_cache("naruto", pagination)
        await engine.search("naruto", pagination)

        assert adapter.call_count["search"] == 2

    async def test_records_metrics(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                search_results=[
                    SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto"),
                    SearchResultDTO(provider_id="provider-a", external_id="2", title="Naruto"),
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        await engine.search("naruto")

        assert engine.metrics.total_aggregations == 1
        assert engine.metrics.total_raw_results == 2
        assert engine.metrics.total_duplicates_merged == 1


class TestLatestAndPopular:
    async def test_get_latest_merges_and_ranks(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                latest=[
                    SearchResultDTO(provider_id="provider-a", external_id="1", title="Frieren")
                ]
            ),
        )
        engine = AggregationEngine(manager=manager)

        results = await engine.get_latest()

        assert len(results) == 1
        assert results[0].title == "Frieren"

    async def test_get_popular_merges_and_ranks(self) -> None:
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

        results = await engine.get_popular()

        assert len(results) == 1


class TestAggregateDetail:
    async def test_merges_detail_from_multiple_providers(self) -> None:
        manager = ProviderManager()
        manager.register(
            PROVIDER_A,
            FakeProviderPort(
                anime_detail=ProviderAnimeDTO(
                    reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
                    title="Attack on Titan",
                    genres=("Action",),
                )
            ),
            priority=5,
        )
        manager.register(
            PROVIDER_B,
            FakeProviderPort(
                anime_detail=ProviderAnimeDTO(
                    reference=ExternalReferenceDTO(provider_id="provider-b", external_id="99"),
                    title="Attack on Titan",
                    genres=("Drama",),
                    rating_score=8.5,
                )
            ),
            priority=1,
        )
        engine = AggregationEngine(manager=manager)

        merged = await engine.aggregate_detail(
            (
                ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
                ExternalReferenceDTO(provider_id="provider-b", external_id="99"),
            )
        )

        assert merged is not None
        assert set(merged.genres) == {"Action", "Drama"}
        assert merged.rating_score == 8.5
        assert {s.provider_id for s in merged.sources} == {"provider-a", "provider-b"}

    async def test_returns_none_for_empty_references(self) -> None:
        engine = make_engine()
        result = await engine.aggregate_detail(())
        assert result is None

    async def test_isolates_a_single_provider_failure(self) -> None:
        manager = ProviderManager()
        manager.register(PROVIDER_A, FailingProviderPort())
        manager.register(
            PROVIDER_B,
            FakeProviderPort(
                anime_detail=ProviderAnimeDTO(
                    reference=ExternalReferenceDTO(provider_id="provider-b", external_id="99"),
                    title="Attack on Titan",
                )
            ),
        )
        engine = AggregationEngine(manager=manager)

        merged = await engine.aggregate_detail(
            (
                ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
                ExternalReferenceDTO(provider_id="provider-b", external_id="99"),
            )
        )

        assert merged is not None
        assert merged.title == "Attack on Titan"
        assert len(merged.sources) == 1

    async def test_returns_none_when_all_providers_fail(self) -> None:
        manager = ProviderManager()
        manager.register(PROVIDER_A, FailingProviderPort())
        engine = AggregationEngine(manager=manager)

        result = await engine.aggregate_detail(
            (ExternalReferenceDTO(provider_id="provider-a", external_id="1"),)
        )

        assert result is None

    async def test_returns_none_when_provider_has_no_detail(self) -> None:
        manager = ProviderManager()
        manager.register(PROVIDER_A, FakeProviderPort(anime_detail=None))
        engine = AggregationEngine(manager=manager)

        result = await engine.aggregate_detail(
            (ExternalReferenceDTO(provider_id="provider-a", external_id="1"),)
        )

        assert result is None

    async def test_caches_merged_detail(self) -> None:
        manager = ProviderManager()
        adapter = FakeProviderPort(
            anime_detail=ProviderAnimeDTO(
                reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
                title="Attack on Titan",
            )
        )
        manager.register(PROVIDER_A, adapter)
        engine = AggregationEngine(manager=manager, cache=InMemoryProviderCache())
        reference = (ExternalReferenceDTO(provider_id="provider-a", external_id="1"),)

        await engine.aggregate_detail(reference)
        await engine.aggregate_detail(reference)

        assert adapter.call_count["get_anime_detail"] == 1


class TestAggregateAllCacheInvalidation:
    async def test_invalidate_all_cache_clears_everything(self) -> None:
        manager = ProviderManager()
        adapter = FakeProviderPort(
            search_results=[
                SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
            ]
        )
        manager.register(PROVIDER_A, adapter)
        engine = AggregationEngine(manager=manager, cache=InMemoryProviderCache())

        await engine.search("naruto")
        await engine.invalidate_all_cache()
        await engine.search("naruto")

        assert adapter.call_count["search"] == 2
