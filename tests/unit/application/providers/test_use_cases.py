from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.use_cases.filter_results import FilterSearchResults
from geekbaku.application.providers.use_cases.get_anime_detail import GetProviderAnimeDetail
from geekbaku.application.providers.use_cases.get_catalog import GetProviderCatalog
from geekbaku.application.providers.use_cases.get_episodes import GetProviderEpisodes
from geekbaku.application.providers.use_cases.get_genres import GetProviderGenres
from geekbaku.application.providers.use_cases.get_latest import GetLatest
from geekbaku.application.providers.use_cases.get_popular import GetPopular
from geekbaku.application.providers.use_cases.get_related import GetProviderRelated
from geekbaku.application.providers.use_cases.get_seasons import GetProviderSeasons
from geekbaku.application.providers.use_cases.normalize_anime import NormalizeAnime
from geekbaku.application.providers.use_cases.search_anime import SearchAnime
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_A = ProviderId("provider-a")


def make_manager_with_provider(**kwargs: object) -> ProviderManager:
    manager = ProviderManager()
    manager.register(PROVIDER_A, FakeProviderPort(**kwargs))  # type: ignore[arg-type]
    return manager


class TestSearchAnime:
    async def test_returns_results_from_registered_provider(self) -> None:
        result = SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
        manager = make_manager_with_provider(search_results=[result])

        results = await SearchAnime(manager).execute("naruto")

        assert results == [result]

    async def test_restricts_search_to_given_provider_ids(self) -> None:
        result = SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
        manager = make_manager_with_provider(search_results=[result])

        results = await SearchAnime(manager).execute("naruto", provider_ids=("provider-a",))

        assert results == [result]


class TestGetProviderAnimeDetail:
    async def test_returns_none_when_provider_has_no_detail(self) -> None:
        manager = make_manager_with_provider(anime_detail=None)

        result = await GetProviderAnimeDetail(manager).execute(
            ExternalReferenceDTO(provider_id="provider-a", external_id="1")
        )

        assert result is None

    async def test_returns_normalized_detail(self) -> None:
        provider_anime = ProviderAnimeDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            title="Attack on Titan",
            raw_type="TV Series",
            raw_status="Currently Airing",
        )
        manager = make_manager_with_provider(anime_detail=provider_anime)

        result = await GetProviderAnimeDetail(manager).execute(
            ExternalReferenceDTO(provider_id="provider-a", external_id="1")
        )

        assert result is not None
        assert result.title == "Attack on Titan"
        assert result.type == "tv"
        assert result.status == "ongoing"
        assert result.slug == "attack-on-titan"


class TestGetProviderEpisodes:
    async def test_returns_normalized_episodes(self) -> None:
        episode = ProviderEpisodeDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            number=1,
            title="Episode 1",
        )
        manager = make_manager_with_provider(episodes=[episode])

        episodes = await GetProviderEpisodes(manager).execute(
            ExternalReferenceDTO(provider_id="provider-a", external_id="1")
        )

        assert len(episodes) == 1
        assert episodes[0].number == 1


class TestGetProviderSeasons:
    async def test_returns_normalized_seasons(self) -> None:
        season = ProviderSeasonDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            number=1,
            title="Season 1",
            episode_count=12,
        )
        manager = make_manager_with_provider(seasons=[season])

        seasons = await GetProviderSeasons(manager).execute(
            ExternalReferenceDTO(provider_id="provider-a", external_id="1")
        )

        assert len(seasons) == 1
        assert seasons[0].number == 1
        assert seasons[0].episode_count == 12


class TestGetProviderRelated:
    async def test_returns_normalized_related(self) -> None:
        related = ProviderRelatedDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="2"),
            title="Attack on Titan Season 2",
            raw_relation_type="Sequel",
        )
        manager = make_manager_with_provider(related=[related])

        results = await GetProviderRelated(manager).execute(
            ExternalReferenceDTO(provider_id="provider-a", external_id="1")
        )

        assert len(results) == 1
        assert results[0].relation_type == "sequel"


class TestGetProviderCatalog:
    async def test_returns_genres_and_types(self) -> None:
        manager = make_manager_with_provider(genres=["Action"], types=["TV"])

        catalog = await GetProviderCatalog(manager).execute("provider-a")

        assert catalog.genres == ("Action",)
        assert catalog.types == ("TV",)


class TestGetProviderGenres:
    async def test_returns_normalized_genres(self) -> None:
        manager = make_manager_with_provider(genres=["  Action  ", "Action", "Isekai"])

        genres = await GetProviderGenres(manager).execute("provider-a")

        assert genres == ("Action", "Isekai")


class TestGetLatestAndPopular:
    async def test_get_latest_returns_results(self) -> None:
        result = SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
        manager = make_manager_with_provider(latest=[result])

        results = await GetLatest(manager).execute()

        assert results == [result]

    async def test_get_popular_returns_results(self) -> None:
        result = SearchResultDTO(provider_id="provider-a", external_id="1", title="Naruto")
        manager = make_manager_with_provider(popular=[result])

        results = await GetPopular(manager).execute()

        assert results == [result]


class TestFilterSearchResults:
    def test_filters_by_type_year_and_provider(self) -> None:
        tv_result = SearchResultDTO(
            provider_id="provider-a", external_id="1", title="A", anime_type="tv", year=2013
        )
        movie_result = SearchResultDTO(
            provider_id="provider-a", external_id="2", title="B", anime_type="movie", year=2020
        )
        other_provider = SearchResultDTO(
            provider_id="provider-b", external_id="3", title="C", anime_type="tv", year=2013
        )
        results = [tv_result, movie_result, other_provider]

        filtered = FilterSearchResults().execute(results, anime_type="tv")
        assert filtered == [tv_result, other_provider]

        filtered = FilterSearchResults().execute(results, year=2020)
        assert filtered == [movie_result]

        filtered = FilterSearchResults().execute(results, provider_id="provider-a")
        assert filtered == [tv_result, movie_result]

    def test_no_filters_returns_all(self) -> None:
        results = [SearchResultDTO(provider_id="provider-a", external_id="1", title="A")]
        assert FilterSearchResults().execute(results) == results


class TestNormalizeAnime:
    def test_normalizes_provider_anime(self) -> None:
        provider_anime = ProviderAnimeDTO(
            reference=ExternalReferenceDTO(provider_id="provider-a", external_id="1"),
            title="Frieren",
            raw_type="Movie",
            raw_status="Finished Airing",
        )

        normalized = NormalizeAnime().execute(provider_anime)

        assert normalized.type == "movie"
        assert normalized.status == "completed"
        assert normalized.slug == "frieren"
