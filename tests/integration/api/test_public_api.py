"""Test de integración de la API pública (Sprint 8): ejercita la app FastAPI
real de punta a punta (`httpx.AsyncClient` sobre el ASGI app, sin servidor
real), con `app.dependency_overrides` inyectando un `CatalogUnitOfWork` y un
`ProviderManager` in-memory — mismo patrón que
`tests/integration/playback/test_playback_api.py` (Sprint 7).
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.providers.dto import SearchResultDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Season, Studio
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    GenreId,
    SeasonId,
    SeasonNumber,
    Slug,
    StudioId,
    Title,
)
from geekbaku.domain.providers.value_objects import ProviderId
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.app import app
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_ID = ProviderId("provider-a")


class SeededCatalog:
    def __init__(self, anime: Anime, episode: Episode, genre: Genre, studio: Studio) -> None:
        self.anime = anime
        self.episode = episode
        self.genre = genre
        self.studio = studio


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_client(client: AsyncClient) -> AsyncIterator[tuple[AsyncClient, SeededCatalog]]:
    uow = FakeCatalogUnitOfWork()

    genre = Genre(id=GenreId.new(), name="Action", slug=Slug("action"))
    await uow.genres.add(genre)
    studio = Studio(id=StudioId.new(), name="Wit Studio", slug=Slug("wit-studio"))
    await uow.studios.add(studio)

    anime = Anime(
        id=AnimeId.new(),
        title=Title("Attack on Titan"),
        slug=Slug("attack-on-titan"),
        anime_type=AnimeType.TV,
    )
    anime.add_genre(genre.id)
    season = Season(id=SeasonId.new(), number=SeasonNumber(1))
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    season.add_episode(episode)
    anime.add_season(season)
    await uow.animes.add(anime)
    uow.register_episode(episode)

    app.dependency_overrides[deps.get_catalog_unit_of_work] = lambda: uow

    manager = ProviderManager()
    manager.register(
        PROVIDER_ID,
        FakeProviderPort(
            search_results=[
                SearchResultDTO(
                    provider_id=str(PROVIDER_ID), external_id="1", title="Attack on Titan"
                )
            ],
            latest=[
                SearchResultDTO(
                    provider_id=str(PROVIDER_ID), external_id="1", title="Attack on Titan"
                )
            ],
            popular=[
                SearchResultDTO(
                    provider_id=str(PROVIDER_ID), external_id="1", title="Attack on Titan"
                )
            ],
        ),
        priority=5,
    )
    engine = AggregationEngine(manager=manager)
    app.dependency_overrides[deps.get_provider_manager] = lambda: manager
    app.dependency_overrides[deps.get_aggregation_engine] = lambda: engine

    yield client, SeededCatalog(anime=anime, episode=episode, genre=genre, studio=studio)


class TestAnimeController:
    async def test_list_anime(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, seeded = seeded_client
        response = await client.get("/api/v1/anime")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(seeded.anime.id)

    async def test_list_anime_filters_by_genre(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, seeded = seeded_client
        response = await client.get("/api/v1/anime", params={"genre_id": str(seeded.genre.id)})

        assert response.status_code == 200
        assert response.json()["total"] == 1

        other_genre_response = await client.get(
            "/api/v1/anime", params={"genre_id": str(GenreId.new())}
        )
        assert other_genre_response.json()["total"] == 0

    async def test_get_anime_by_id(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, seeded = seeded_client
        response = await client.get(f"/api/v1/anime/{seeded.anime.id}")

        assert response.status_code == 200
        assert response.json()["title"] == "Attack on Titan"

    async def test_get_anime_by_id_returns_404(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, _seeded = seeded_client
        response = await client.get(f"/api/v1/anime/{AnimeId.new()}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    async def test_get_anime_episodes(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, seeded = seeded_client
        response = await client.get(f"/api/v1/anime/{seeded.anime.id}/episodes")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(seeded.episode.id)


class TestEpisodeController:
    async def test_get_episode_by_id(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, seeded = seeded_client
        response = await client.get(f"/api/v1/episodes/{seeded.episode.id}")

        assert response.status_code == 200
        assert response.json()["title"] == "Episode 1"

    async def test_get_episode_by_id_returns_404(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, _seeded = seeded_client
        response = await client.get(f"/api/v1/episodes/{EpisodeId.new()}")

        assert response.status_code == 404


class TestSearchController:
    async def test_search(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/search", params={"q": "attack on titan"})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["title"] == "Attack on Titan"
        assert body[0]["sources"][0]["provider_id"] == "provider-a"

    async def test_search_requires_query(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/search")

        assert response.status_code == 422

    async def test_latest(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/latest")

        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_popular(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/popular")

        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_search_with_no_providers_returns_empty_list(
        self, client: AsyncClient
    ) -> None:
        uow = FakeCatalogUnitOfWork()
        app.dependency_overrides[deps.get_catalog_unit_of_work] = lambda: uow
        # Desde el Sprint 10 el `ProviderManager` por defecto trae el
        # adapter de AnimeFLV wireado — para probar específicamente el
        # caso "sin providers registrados" hay que sobreescribirlo con
        # uno vacío, no alcanza con dejar el default.
        empty_manager = ProviderManager()
        app.dependency_overrides[deps.get_provider_manager] = lambda: empty_manager
        app.dependency_overrides[deps.get_aggregation_engine] = lambda: AggregationEngine(
            manager=empty_manager
        )

        response = await client.get("/api/v1/search", params={"q": "anything"})

        assert response.status_code == 200
        assert response.json() == []


class TestGenreController:
    async def test_list_genres(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/genres")

        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_get_genre_by_id(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, seeded = seeded_client
        response = await client.get(f"/api/v1/genres/{seeded.genre.id}")

        assert response.status_code == 200
        assert response.json()["slug"] == "action"

    async def test_get_genre_by_id_returns_404(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, _seeded = seeded_client
        response = await client.get(f"/api/v1/genres/{GenreId.new()}")

        assert response.status_code == 404


class TestCatalogController:
    async def test_get_catalog_facets(
        self, seeded_client: tuple[AsyncClient, SeededCatalog]
    ) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/catalog")

        assert response.status_code == 200
        body = response.json()
        assert "tv" in body["types"]
        assert "ongoing" in body["statuses"]
        assert len(body["genres"]) == 1
        assert len(body["studios"]) == 1


class TestProviderController:
    async def test_list_providers(self, seeded_client: tuple[AsyncClient, SeededCatalog]) -> None:
        client, _seeded = seeded_client
        response = await client.get("/api/v1/providers")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["provider_id"] == "provider-a"
        assert body[0]["priority"] == 5

    async def test_list_providers_empty_when_manager_has_none_registered(
        self, client: AsyncClient
    ) -> None:
        # Ver nota en `test_search_with_no_providers_returns_empty_list`:
        # el default ya no está vacío desde el Sprint 10.
        app.dependency_overrides[deps.get_provider_manager] = lambda: ProviderManager()

        response = await client.get("/api/v1/providers")

        assert response.status_code == 200
        assert response.json() == []

    async def test_list_providers_includes_tioanime_by_default(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/v1/providers")

        assert response.status_code == 200
        body = response.json()
        assert any(p["provider_id"] == "tioanime" for p in body)


class TestHealthController:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
