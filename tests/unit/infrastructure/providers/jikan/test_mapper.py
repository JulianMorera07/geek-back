"""Tests unitarios puros de `mapper.py`: JSON crudo de Jikan (fixtures
representativas, sin HTTP) -> DTOs de GeekBaku. Ver `test_adapter.py`
(integración, con `respx`) para el flujo completo con HTTP mockeado.
"""

from geekbaku.infrastructure.providers.jikan.mapper import (
    PROVIDER_ID,
    STATIC_ANIME_TYPES,
    map_anime_detail,
    map_episode,
    map_genre_names,
    map_relation_group,
    map_search_result,
    map_season,
    to_external_reference,
)

SEARCH_RESULT_RAW = {
    "mal_id": 16498,
    "title": "Shingeki no Kyojin",
    "type": "TV",
    "year": 2013,
    "images": {"jpg": {"image_url": "https://cdn.myanimelist.net/small.jpg", "large_image_url": "https://cdn.myanimelist.net/large.jpg"}},
}

ANIME_DETAIL_RAW = {
    "mal_id": 16498,
    "title": "Shingeki no Kyojin",
    "synopsis": "Humanity fights titans.",
    "type": "TV",
    "status": "Finished Airing",
    "episodes": 25,
    "score": 8.5,
    "genres": [{"mal_id": 1, "name": "Action"}, {"mal_id": 8, "name": "Drama"}],
    "themes": [{"mal_id": 58, "name": "Gore"}],
    "demographics": [{"mal_id": 27, "name": "Shounen"}],
    "studios": [{"mal_id": 858, "name": "Wit Studio"}],
    "images": {"jpg": {"large_image_url": "https://cdn.myanimelist.net/large.jpg"}},
    "trailer": {"url": "https://www.youtube.com/watch?v=abc123"},
}

EPISODE_RAW = {
    "mal_id": 1,
    "title": "To You, in 2000 Years",
    "aired": "2013-04-07T00:00:00+00:00",
}

RELATION_GROUP_RAW = {
    "relation": "Sequel",
    "entry": [
        {"mal_id": 25777, "type": "anime", "name": "Shingeki no Kyojin Season 2"},
        {"mal_id": 99999, "type": "manga", "name": "Some Manga Spin-off"},
    ],
}

GENRES_RESPONSE_RAW = {"data": [{"mal_id": 1, "name": "Action"}, {"mal_id": 2, "name": "Isekai"}]}


class TestMapSearchResult:
    def test_maps_all_fields(self) -> None:
        result = map_search_result(SEARCH_RESULT_RAW)

        assert result.provider_id == PROVIDER_ID
        assert result.external_id == "16498"
        assert result.title == "Shingeki no Kyojin"
        assert result.anime_type == "TV"
        assert result.year == 2013
        assert result.thumbnail_url == "https://cdn.myanimelist.net/large.jpg"

    def test_falls_back_to_small_image_when_no_large_image(self) -> None:
        raw = {
            "mal_id": 1,
            "title": "X",
            "images": {"jpg": {"image_url": "https://cdn.myanimelist.net/small.jpg"}},
        }
        result = map_search_result(raw)
        assert result.thumbnail_url == "https://cdn.myanimelist.net/small.jpg"

    def test_handles_missing_optional_fields(self) -> None:
        result = map_search_result({"mal_id": 1, "title": "X"})
        assert result.thumbnail_url is None
        assert result.year is None


class TestMapAnimeDetail:
    def test_maps_all_fields(self) -> None:
        detail = map_anime_detail(ANIME_DETAIL_RAW)

        assert detail.reference.provider_id == PROVIDER_ID
        assert detail.reference.external_id == "16498"
        assert detail.title == "Shingeki no Kyojin"
        assert detail.raw_type == "TV"
        assert detail.raw_status == "Finished Airing"
        assert detail.country_code == "JP"
        assert detail.genres == ("Action", "Drama")
        assert detail.tags == ("Gore", "Shounen")
        assert detail.studios == ("Wit Studio",)
        assert detail.rating_score == 8.5
        assert detail.episode_count == 25
        assert detail.trailer_url == "https://www.youtube.com/watch?v=abc123"
        assert detail.banner_url is None

    def test_handles_missing_optional_sections(self) -> None:
        detail = map_anime_detail({"mal_id": 1, "title": "X"})
        assert detail.genres == ()
        assert detail.tags == ()
        assert detail.studios == ()
        assert detail.trailer_url is None
        assert detail.thumbnail_url is None


class TestMapEpisode:
    def test_maps_all_fields(self) -> None:
        episode = map_episode(EPISODE_RAW, anime_mal_id="16498")

        assert episode.reference.provider_id == PROVIDER_ID
        assert episode.reference.external_id == "16498:1"
        assert episode.number == 1
        assert episode.title == "To You, in 2000 Years"
        assert episode.air_date is not None
        assert episode.air_date.isoformat() == "2013-04-07"

    def test_handles_missing_aired_date(self) -> None:
        episode = map_episode({"mal_id": 2, "title": "Ep 2"}, anime_mal_id="16498")
        assert episode.air_date is None

    def test_handles_malformed_aired_date(self) -> None:
        episode = map_episode(
            {"mal_id": 2, "title": "Ep 2", "aired": "not-a-date"}, anime_mal_id="16498"
        )
        assert episode.air_date is None


class TestMapSeason:
    def test_derives_single_season_from_anime_detail(self) -> None:
        reference = to_external_reference("16498")

        season = map_season(ANIME_DETAIL_RAW, reference)

        assert season.number == 1
        assert season.episode_count == 25
        assert season.title == "Shingeki no Kyojin"


class TestMapRelationGroup:
    def test_maps_anime_entries_and_skips_non_anime(self) -> None:
        related = map_relation_group(RELATION_GROUP_RAW)

        assert len(related) == 1
        assert related[0].reference.external_id == "25777"
        assert related[0].title == "Shingeki no Kyojin Season 2"
        assert related[0].raw_relation_type == "Sequel"

    def test_empty_entry_list_yields_no_related(self) -> None:
        assert map_relation_group({"relation": "Sequel", "entry": []}) == []


class TestMapGenreNames:
    def test_extracts_names(self) -> None:
        assert map_genre_names(GENRES_RESPONSE_RAW) == ["Action", "Isekai"]

    def test_handles_missing_data(self) -> None:
        assert map_genre_names({}) == []


class TestStaticAnimeTypes:
    def test_is_non_empty_and_contains_tv(self) -> None:
        assert "TV" in STATIC_ANIME_TYPES
        assert len(STATIC_ANIME_TYPES) > 0
