from geekbaku.application.aggregation.dto import (
    AggregatedAnimeDTO,
    AggregatedSearchResultDTO,
    SourceReference,
)
from geekbaku.application.aggregation.ranking import (
    completeness_score_anime,
    completeness_score_search,
    quality_score_anime,
    quality_score_search,
    rank_anime,
    rank_search_results,
)


def make_source(
    provider_id: str, priority: int = 0, response_time_ms: float = 0.0
) -> SourceReference:
    return SourceReference(
        provider_id=provider_id,
        external_id="1",
        priority=priority,
        response_time_ms=response_time_ms,
    )


def make_aggregated_anime(**overrides: object) -> AggregatedAnimeDTO:
    defaults: dict[str, object] = {
        "title": "Attack on Titan",
        "slug": "attack-on-titan",
        "synopsis": None,
        "type": "tv",
        "status": "ongoing",
        "country_code": None,
        "thumbnail_url": None,
        "banner_url": None,
        "trailer_url": None,
        "rating_score": None,
        "sources": (make_source("provider-a", priority=1),),
    }
    defaults.update(overrides)
    return AggregatedAnimeDTO(**defaults)  # type: ignore[arg-type]


def make_aggregated_search_result(**overrides: object) -> AggregatedSearchResultDTO:
    defaults: dict[str, object] = {
        "title": "Attack on Titan",
        "thumbnail_url": None,
        "anime_type": None,
        "year": None,
        "sources": (make_source("provider-a", priority=1),),
    }
    defaults.update(overrides)
    return AggregatedSearchResultDTO(**defaults)  # type: ignore[arg-type]


class TestCompletenessScoreAnime:
    def test_empty_result_scores_zero(self) -> None:
        item = make_aggregated_anime()
        assert completeness_score_anime(item) == 0.0

    def test_fully_populated_result_scores_one(self) -> None:
        item = make_aggregated_anime(
            synopsis="...",
            thumbnail_url="https://x/t.jpg",
            banner_url="https://x/b.jpg",
            trailer_url="https://x/tr.mp4",
            rating_score=8.0,
            genres=("Action",),
            studios=("Wit",),
            producers=("Aniplex",),
            tags=("Gore",),
            external_ids=(),
        )
        # external_ids vacío deliberadamente: no debería alcanzar 1.0
        assert completeness_score_anime(item) == 0.9

    def test_partial_result_is_between_zero_and_one(self) -> None:
        item = make_aggregated_anime(synopsis="...", genres=("Action",))
        score = completeness_score_anime(item)
        assert 0.0 < score < 1.0


class TestCompletenessScoreSearch:
    def test_empty_result_scores_zero(self) -> None:
        assert completeness_score_search(make_aggregated_search_result()) == 0.0

    def test_fully_populated_result_scores_one(self) -> None:
        item = make_aggregated_search_result(
            thumbnail_url="https://x/t.jpg", anime_type="tv", year=2013
        )
        assert completeness_score_search(item) == 1.0


class TestQualityScore:
    def test_anime_without_rating_is_neutral(self) -> None:
        assert quality_score_anime(make_aggregated_anime(rating_score=None)) == 0.5

    def test_anime_rating_is_normalized_to_0_1(self) -> None:
        assert quality_score_anime(make_aggregated_anime(rating_score=8.0)) == 0.8

    def test_anime_rating_is_clamped(self) -> None:
        assert quality_score_anime(make_aggregated_anime(rating_score=15.0)) == 1.0

    def test_search_result_quality_is_always_neutral(self) -> None:
        assert quality_score_search(make_aggregated_search_result()) == 0.5


class TestRankAnime:
    def test_higher_priority_wins_first(self) -> None:
        low = make_aggregated_anime(
            title="Low", sources=(make_source("provider-a", priority=1),)
        )
        high = make_aggregated_anime(
            title="High", sources=(make_source("provider-b", priority=10),)
        )

        ranked = rank_anime([low, high])

        assert [item.title for item in ranked] == ["High", "Low"]

    def test_quality_breaks_priority_ties(self) -> None:
        worse = make_aggregated_anime(
            title="Worse", rating_score=3.0, sources=(make_source("provider-a", priority=5),)
        )
        better = make_aggregated_anime(
            title="Better", rating_score=9.0, sources=(make_source("provider-b", priority=5),)
        )

        ranked = rank_anime([worse, better])

        assert [item.title for item in ranked] == ["Better", "Worse"]

    def test_response_time_breaks_remaining_ties(self) -> None:
        slow = make_aggregated_anime(
            title="Slow", sources=(make_source("provider-a", priority=5, response_time_ms=500),)
        )
        fast = make_aggregated_anime(
            title="Fast", sources=(make_source("provider-b", priority=5, response_time_ms=50),)
        )

        ranked = rank_anime([slow, fast])

        assert [item.title for item in ranked] == ["Fast", "Slow"]

    def test_populates_scores_on_output(self) -> None:
        item = make_aggregated_anime(rating_score=8.0)
        ranked = rank_anime([item])
        assert ranked[0].quality_score == 0.8


class TestRankSearchResults:
    def test_orders_by_priority_then_completeness(self) -> None:
        sparse_high_priority = make_aggregated_search_result(
            title="Sparse", sources=(make_source("provider-a", priority=10),)
        )
        rich_low_priority = make_aggregated_search_result(
            title="Rich",
            thumbnail_url="https://x/t.jpg",
            anime_type="tv",
            year=2013,
            sources=(make_source("provider-b", priority=1),),
        )

        ranked = rank_search_results([sparse_high_priority, rich_low_priority])

        assert [item.title for item in ranked] == ["Sparse", "Rich"]
