"""Tests de integración de `JikanProviderAdapter`.

Usan `respx` para interceptar las peticiones HTTP en el nivel de transporte
de `httpx` (nunca hay red real), verificando en conjunto: construcción de
URL/params, parsing de la respuesta y mapeo a los DTOs de GeekBaku — el
mismo camino que recorrería una llamada real, sin depender de que la API
pública de Jikan esté disponible durante el test.
"""

import httpx
import pytest
import respx

from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId
from geekbaku.infrastructure.providers.jikan.adapter import JikanProviderAdapter
from geekbaku.infrastructure.providers.jikan.client import JikanClient

BASE_URL = "https://api.jikan.moe/v4"


def make_adapter() -> JikanProviderAdapter:
    http_client = httpx.AsyncClient()
    return JikanProviderAdapter(JikanClient(http_client, base_url=BASE_URL))


REFERENCE = ExternalReference(provider_id=ProviderId("jikan"), external_id="16498")


class TestSearch:
    @respx.mock
    async def test_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"mal_id": 16498, "title": "Shingeki no Kyojin", "type": "TV", "year": 2013}
                    ]
                },
            )
        )
        adapter = make_adapter()

        results = await adapter.search("shingeki", Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].provider_id == "jikan"
        assert results[0].title == "Shingeki no Kyojin"

    @respx.mock
    async def test_sends_query_and_pagination_params(self) -> None:
        route = respx.get(f"{BASE_URL}/anime").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        adapter = make_adapter()

        await adapter.search("naruto", Pagination(page=2, page_size=10))

        assert route.called
        request = route.calls.last.request
        assert request.url.params["q"] == "naruto"
        assert request.url.params["page"] == "2"
        assert request.url.params["limit"] == "10"


class TestGetAnimeDetail:
    @respx.mock
    async def test_returns_normalized_detail(self) -> None:
        respx.get(f"{BASE_URL}/anime/16498/full").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "mal_id": 16498,
                        "title": "Shingeki no Kyojin",
                        "type": "TV",
                        "status": "Finished Airing",
                        "episodes": 25,
                        "genres": [{"mal_id": 1, "name": "Action"}],
                    }
                },
            )
        )
        adapter = make_adapter()

        detail = await adapter.get_anime_detail(REFERENCE)

        assert detail is not None
        assert detail.title == "Shingeki no Kyojin"
        assert detail.genres == ("Action",)
        assert detail.country_code == "JP"

    @respx.mock
    async def test_returns_none_on_404(self) -> None:
        respx.get(f"{BASE_URL}/anime/999999999/full").mock(
            return_value=httpx.Response(404, json={"status": 404, "message": "Not found"})
        )
        adapter = make_adapter()
        reference = ExternalReference(provider_id=ProviderId("jikan"), external_id="999999999")

        detail = await adapter.get_anime_detail(reference)

        assert detail is None

    @respx.mock
    async def test_propagates_non_404_http_errors(self) -> None:
        respx.get(f"{BASE_URL}/anime/16498/full").mock(return_value=httpx.Response(500))
        adapter = make_adapter()

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.get_anime_detail(REFERENCE)


class TestGetEpisodes:
    @respx.mock
    async def test_returns_normalized_episodes(self) -> None:
        respx.get(f"{BASE_URL}/anime/16498/episodes").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"mal_id": 1, "title": "Ep 1", "aired": "2013-04-07T00:00:00+00:00"},
                        {"mal_id": 2, "title": "Ep 2", "aired": None},
                    ]
                },
            )
        )
        adapter = make_adapter()

        episodes = await adapter.get_episodes(REFERENCE)

        assert len(episodes) == 2
        assert episodes[0].reference.external_id == "16498:1"
        assert episodes[0].air_date is not None
        assert episodes[1].air_date is None


class TestGetSeasons:
    @respx.mock
    async def test_derives_single_season_from_detail(self) -> None:
        respx.get(f"{BASE_URL}/anime/16498/full").mock(
            return_value=httpx.Response(
                200, json={"data": {"mal_id": 16498, "title": "Shingeki no Kyojin", "episodes": 25}}
            )
        )
        adapter = make_adapter()

        seasons = await adapter.get_seasons(REFERENCE)

        assert len(seasons) == 1
        assert seasons[0].number == 1
        assert seasons[0].episode_count == 25


class TestGetRelated:
    @respx.mock
    async def test_returns_normalized_related(self) -> None:
        respx.get(f"{BASE_URL}/anime/16498/relations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "relation": "Sequel",
                            "entry": [
                                {"mal_id": 25777, "type": "anime", "name": "Season 2"},
                            ],
                        }
                    ]
                },
            )
        )
        adapter = make_adapter()

        related = await adapter.get_related(REFERENCE)

        assert len(related) == 1
        assert related[0].raw_relation_type == "Sequel"


class TestGetLatestAndPopular:
    @respx.mock
    async def test_get_latest_hits_seasons_now(self) -> None:
        respx.get(f"{BASE_URL}/seasons/now").mock(
            return_value=httpx.Response(
                200, json={"data": [{"mal_id": 1, "title": "Currently Airing Anime"}]}
            )
        )
        adapter = make_adapter()

        results = await adapter.get_latest(Pagination())

        assert len(results) == 1
        assert results[0].title == "Currently Airing Anime"

    @respx.mock
    async def test_get_popular_hits_top_anime(self) -> None:
        respx.get(f"{BASE_URL}/top/anime").mock(
            return_value=httpx.Response(200, json={"data": [{"mal_id": 1, "title": "Top Anime"}]})
        )
        adapter = make_adapter()

        results = await adapter.get_popular(Pagination())

        assert len(results) == 1
        assert results[0].title == "Top Anime"


class TestGetGenresAndTypes:
    @respx.mock
    async def test_get_genres_hits_genres_endpoint(self) -> None:
        respx.get(f"{BASE_URL}/genres/anime").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"mal_id": 1, "name": "Action"}, {"mal_id": 2, "name": "Isekai"}]
                },
            )
        )
        adapter = make_adapter()

        genres = await adapter.get_genres()

        assert genres == ["Action", "Isekai"]

    async def test_get_types_is_static_and_needs_no_http(self) -> None:
        adapter = make_adapter()
        types = await adapter.get_types()
        assert "TV" in types
