from geekbaku.application.aggregation.deduplication import (
    are_same_anime,
    group_normalized_anime,
    group_search_results,
    merge_normalized_anime,
    merge_search_results,
    titles_are_similar,
)
from geekbaku.application.providers.dto import (
    NormalizedAnimeDTO,
    NormalizedExternalIdDTO,
    SearchResultDTO,
)


def make_search_result(
    provider_id: str,
    external_id: str,
    title: str,
    anime_type: str | None = "tv",
    **overrides: object,
) -> SearchResultDTO:
    defaults: dict[str, object] = {
        "provider_id": provider_id,
        "external_id": external_id,
        "title": title,
        "anime_type": anime_type,
    }
    defaults.update(overrides)
    return SearchResultDTO(**defaults)  # type: ignore[arg-type]


def make_normalized_anime(
    provider_id: str, external_id: str, title: str, **overrides: object
) -> NormalizedAnimeDTO:
    defaults: dict[str, object] = {
        "provider_id": provider_id,
        "external_id": external_id,
        "title": title,
        "slug": title.lower().replace(" ", "-"),
        "synopsis": None,
        "type": "tv",
        "status": "ongoing",
        "country_code": None,
        "thumbnail_url": None,
        "banner_url": None,
        "trailer_url": None,
        "rating_score": None,
        "genres": (),
        "studios": (),
        "producers": (),
        "tags": (),
        "external_ids": (),
    }
    defaults.update(overrides)
    return NormalizedAnimeDTO(**defaults)  # type: ignore[arg-type]


class TestTitlesAreSimilar:
    def test_identical_titles_match(self) -> None:
        assert titles_are_similar("Attack on Titan", "Attack on Titan") is True

    def test_case_and_punctuation_insensitive(self) -> None:
        assert titles_are_similar("Attack on Titan", "attack-on-titan!!") is True

    def test_different_titles_do_not_match(self) -> None:
        assert titles_are_similar("Attack on Titan", "One Piece") is False

    def test_empty_titles_never_match(self) -> None:
        assert titles_are_similar("", "") is False


class TestGroupSearchResults:
    def test_groups_matching_titles_across_providers(self) -> None:
        a = make_search_result("provider-a", "1", "Attack on Titan")
        b = make_search_result("provider-b", "99", "Attack on Titan")
        c = make_search_result("provider-a", "2", "One Piece")

        groups = group_search_results([a, b, c])

        assert len(groups) == 2
        assert {a, b}.issubset(set(next(g for g in groups if len(g) == 2)))

    def test_different_types_are_not_grouped_even_with_same_title(self) -> None:
        a = make_search_result("provider-a", "1", "Attack on Titan", anime_type="tv")
        b = make_search_result("provider-b", "2", "Attack on Titan", anime_type="movie")

        groups = group_search_results([a, b])

        assert len(groups) == 2

    def test_no_results_yields_no_groups(self) -> None:
        assert group_search_results([]) == []


class TestMergeSearchResults:
    def test_prefers_highest_priority_providers_title(self) -> None:
        low = make_search_result("provider-low", "1", "attack on titan (low)")
        high = make_search_result("provider-high", "2", "Attack on Titan")
        priorities = {"provider-low": 1, "provider-high": 10}

        merged = merge_search_results([low, high], priorities, {})

        assert merged.title == "Attack on Titan"

    def test_keeps_a_source_reference_per_provider(self) -> None:
        a = make_search_result("provider-a", "1", "Attack on Titan")
        b = make_search_result("provider-b", "2", "Attack on Titan")

        merged = merge_search_results([a, b], {"provider-a": 5, "provider-b": 1}, {})

        assert {s.provider_id for s in merged.sources} == {"provider-a", "provider-b"}

    def test_fills_missing_thumbnail_from_any_source(self) -> None:
        a = make_search_result("provider-a", "1", "Attack on Titan", thumbnail_url=None)
        b = make_search_result(
            "provider-b", "2", "Attack on Titan", thumbnail_url="https://cdn.example.com/t.jpg"
        )

        merged = merge_search_results([a, b], {"provider-a": 10, "provider-b": 1}, {})

        assert merged.thumbnail_url == "https://cdn.example.com/t.jpg"

    def test_discards_malformed_thumbnail_url(self) -> None:
        a = make_search_result("provider-a", "1", "Attack on Titan", thumbnail_url="not-a-url")

        merged = merge_search_results([a], {"provider-a": 1}, {})

        assert merged.thumbnail_url is None


class TestAreSameAnime:
    def test_matches_on_shared_external_id(self) -> None:
        a = make_normalized_anime(
            "provider-a", "1", "Shingeki no Kyojin",
            external_ids=(NormalizedExternalIdDTO(source="mal", value="16498"),),
        )
        b = make_normalized_anime(
            "provider-b", "99", "Attack on Titan (totally different title)",
            external_ids=(NormalizedExternalIdDTO(source="mal", value="16498"),),
        )

        assert are_same_anime(a, b) is True

    def test_matches_on_similar_title_and_type(self) -> None:
        a = make_normalized_anime("provider-a", "1", "Attack on Titan")
        b = make_normalized_anime("provider-b", "2", "Attack on Titan")

        assert are_same_anime(a, b) is True

    def test_does_not_match_different_anime(self) -> None:
        a = make_normalized_anime("provider-a", "1", "Attack on Titan")
        b = make_normalized_anime("provider-b", "2", "One Piece")

        assert are_same_anime(a, b) is False


class TestGroupNormalizedAnime:
    def test_groups_by_external_id_across_providers(self) -> None:
        a = make_normalized_anime(
            "provider-a", "1", "Shingeki no Kyojin",
            external_ids=(NormalizedExternalIdDTO(source="mal", value="16498"),),
        )
        b = make_normalized_anime(
            "provider-b", "99", "Attack on Titan",
            external_ids=(NormalizedExternalIdDTO(source="mal", value="16498"),),
        )
        c = make_normalized_anime("provider-a", "2", "One Piece")

        groups = group_normalized_anime([a, b, c])

        assert len(groups) == 2


class TestMergeNormalizedAnime:
    def test_unions_genres_studios_producers_tags_without_duplicates(self) -> None:
        a = make_normalized_anime(
            "provider-a",
            "1",
            "Attack on Titan",
            genres=("Action",),
            studios=("Wit Studio",),
            producers=("Production I.G",),
            tags=("Gore",),
        )
        b = make_normalized_anime(
            "provider-b", "2", "Attack on Titan",
            genres=("Action", "Drama"), studios=("MAPPA",), producers=(), tags=("Gore", "Shounen"),
        )

        merged = merge_normalized_anime([a, b], {"provider-a": 1, "provider-b": 1}, {})

        assert merged.genres == ("Action", "Drama")
        assert set(merged.studios) == {"Wit Studio", "MAPPA"}
        assert merged.producers == ("Production I.G",)
        assert set(merged.tags) == {"Gore", "Shounen"}

    def test_merges_external_ids_from_all_sources(self) -> None:
        a = make_normalized_anime(
            "provider-a", "1", "Attack on Titan",
            external_ids=(NormalizedExternalIdDTO(source="mal", value="16498"),),
        )
        b = make_normalized_anime(
            "provider-b", "2", "Attack on Titan",
            external_ids=(NormalizedExternalIdDTO(source="anilist", value="5114"),),
        )

        merged = merge_normalized_anime([a, b], {"provider-a": 1, "provider-b": 1}, {})

        assert {(e.source, e.value) for e in merged.external_ids} == {
            ("mal", "16498"),
            ("anilist", "5114"),
        }

    def test_prefers_primary_providers_title_and_status(self) -> None:
        low = make_normalized_anime("provider-low", "1", "attack on titan", status="completed")
        high = make_normalized_anime("provider-high", "2", "Attack on Titan", status="ongoing")

        merged = merge_normalized_anime(
            [low, high], {"provider-low": 1, "provider-high": 10}, {}
        )

        assert merged.title == "Attack on Titan"
        assert merged.status == "ongoing"

    def test_averages_rating_score_across_sources_that_report_it(self) -> None:
        a = make_normalized_anime("provider-a", "1", "Attack on Titan", rating_score=8.0)
        b = make_normalized_anime("provider-b", "2", "Attack on Titan", rating_score=9.0)
        c = make_normalized_anime("provider-c", "3", "Attack on Titan", rating_score=None)

        merged = merge_normalized_anime(
            [a, b, c], {"provider-a": 1, "provider-b": 1, "provider-c": 1}, {}
        )

        assert merged.rating_score == 8.5

    def test_keeps_source_reference_per_contributing_provider(self) -> None:
        a = make_normalized_anime("provider-a", "1", "Attack on Titan")
        b = make_normalized_anime("provider-b", "2", "Attack on Titan")

        merged = merge_normalized_anime([a, b], {"provider-a": 5, "provider-b": 3}, {})

        assert {(s.provider_id, s.priority) for s in merged.sources} == {
            ("provider-a", 5),
            ("provider-b", 3),
        }
