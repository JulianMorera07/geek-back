import pytest

from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    ProviderSourceDTO,
)
from geekbaku.application.providers.normalizers import (
    DEFAULT_ANIME_STATUS,
    DEFAULT_ANIME_TYPE,
    DEFAULT_RELATION_TYPE,
    normalize_genre_names,
    normalize_relation_type,
    normalize_status,
    normalize_type,
    slugify,
    to_normalized_anime,
    to_normalized_episode,
    to_normalized_related,
    to_normalized_season,
)
from geekbaku.domain.catalog.value_objects import AnimeStatus, AnimeType, RelationType


class TestNormalizeType:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("TV Series", AnimeType.TV),
            ("Movie", AnimeType.MOVIE),
            ("OVA", AnimeType.OVA),
            ("ONA", AnimeType.ONA),
            ("Special", AnimeType.SPECIAL),
            ("Music Video", AnimeType.MUSIC),
        ],
    )
    def test_matches_known_keywords(self, raw: str, expected: AnimeType) -> None:
        assert normalize_type(raw) == expected

    def test_defaults_when_none(self) -> None:
        assert normalize_type(None) == DEFAULT_ANIME_TYPE

    def test_defaults_when_unrecognized(self) -> None:
        assert normalize_type("Unknown Format") == DEFAULT_ANIME_TYPE


class TestNormalizeStatus:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Currently Airing", AnimeStatus.ONGOING),
            ("Finished Airing", AnimeStatus.COMPLETED),
            ("Not yet aired", AnimeStatus.ANNOUNCED),
            ("On Hiatus", AnimeStatus.PAUSED),
            ("Cancelled", AnimeStatus.CANCELLED),
        ],
    )
    def test_matches_known_keywords(self, raw: str, expected: AnimeStatus) -> None:
        assert normalize_status(raw) == expected

    def test_defaults_when_none(self) -> None:
        assert normalize_status(None) == DEFAULT_ANIME_STATUS

    def test_defaults_when_unrecognized(self) -> None:
        assert normalize_status("???") == DEFAULT_ANIME_STATUS


class TestNormalizeRelationType:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Sequel", RelationType.SEQUEL),
            ("Prequel", RelationType.PREQUEL),
            ("Side Story", RelationType.SIDE_STORY),
            ("Parent Story", RelationType.PARENT_STORY),
            ("Spin-off", RelationType.SPIN_OFF),
            ("Alternative Version", RelationType.ALTERNATIVE_VERSION),
            ("Adaptation", RelationType.ADAPTATION),
            ("Summary", RelationType.SUMMARY),
        ],
    )
    def test_matches_known_keywords(self, raw: str, expected: RelationType) -> None:
        assert normalize_relation_type(raw) == expected

    def test_defaults_when_none(self) -> None:
        assert normalize_relation_type(None) == DEFAULT_RELATION_TYPE

    def test_defaults_when_unrecognized(self) -> None:
        assert normalize_relation_type("???") == DEFAULT_RELATION_TYPE


class TestNormalizeGenreNames:
    def test_strips_whitespace_and_collapses_internal_spaces(self) -> None:
        assert normalize_genre_names(["  Action  ", "Sci   Fi"]) == ("Action", "Sci Fi")

    def test_drops_empty_entries(self) -> None:
        assert normalize_genre_names(["Action", "   ", ""]) == ("Action",)

    def test_deduplicates_preserving_order(self) -> None:
        assert normalize_genre_names(["Action", "Isekai", "Action"]) == ("Action", "Isekai")


class TestSlugify:
    def test_generates_kebab_case(self) -> None:
        assert slugify("Attack on Titan") == "attack-on-titan"

    def test_strips_invalid_characters(self) -> None:
        assert slugify("Naruto: Shippuden!") == "naruto-shippuden"

    def test_falls_back_when_empty(self) -> None:
        assert slugify("   ") == "untitled"


class TestToNormalizedAnime:
    def test_maps_all_fields(self) -> None:
        provider_anime = ProviderAnimeDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            title="Attack on Titan",
            synopsis="Humanity fights titans.",
            raw_type="TV Series",
            raw_status="Currently Airing",
            country_code="JP",
            genres=("Action",),
            studios=("MAPPA",),
            tags=("dark-fantasy",),
            thumbnail_url="https://cdn.example.com/t.jpg",
            banner_url="https://cdn.example.com/b.jpg",
            trailer_url="https://cdn.example.com/tr.mp4",
            rating_score=8.5,
        )

        normalized = to_normalized_anime(provider_anime)

        assert normalized.provider_id == "provider-a"
        assert normalized.external_id == "1"
        assert normalized.slug == "attack-on-titan"
        assert normalized.type == "tv"
        assert normalized.status == "ongoing"
        assert normalized.genres == ("Action",)


class TestToNormalizedEpisode:
    def test_maps_all_fields(self) -> None:
        provider_episode = ProviderEpisodeDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            number=1,
            title="The Beginning",
            thumbnail_url="https://cdn.example.com/ep1.jpg",
            sources=(ProviderSourceDTO(url="https://cdn.example.com/ep1.m3u8", quality="hd"),),
        )

        normalized = to_normalized_episode(provider_episode)

        assert normalized.provider_id == "provider-a"
        assert normalized.number == 1
        assert normalized.sources[0].quality == "hd"


class TestToNormalizedSeason:
    def test_maps_all_fields(self) -> None:
        provider_season = ProviderSeasonDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            number=2,
            title="Season 2",
            episode_count=25,
        )

        normalized = to_normalized_season(provider_season)

        assert normalized.provider_id == "provider-a"
        assert normalized.external_id == "1"
        assert normalized.number == 2
        assert normalized.title == "Season 2"
        assert normalized.episode_count == 25


class TestToNormalizedRelated:
    def test_maps_and_normalizes_relation_type(self) -> None:
        provider_related = ProviderRelatedDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="2"),
            title="Attack on Titan Season 2",
            raw_relation_type="Sequel",
        )

        normalized = to_normalized_related(provider_related)

        assert normalized.provider_id == "provider-a"
        assert normalized.external_id == "2"
        assert normalized.title == "Attack on Titan Season 2"
        assert normalized.relation_type == "sequel"
