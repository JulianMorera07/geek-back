"""Test de integración del endpoint puente entre resultados externos
(provider) y el catálogo interno (`GET /anime/external/{provider_id}/{external_id}`,
Sprint 10 hotfix): ejercita la app FastAPI real de punta a punta, con
`app.dependency_overrides` inyectando un `CatalogUnitOfWork` vacío y un
`ProviderManager` con un `FakeProviderPort` configurado — mismo patrón que
`test_public_api.py`.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderSourceDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import ProviderId
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.app import app
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_ID = ProviderId("animeflv")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    uow = FakeCatalogUnitOfWork()
    manager = ProviderManager()
    manager.register(
        PROVIDER_ID,
        FakeProviderPort(
            anime_detail=ProviderAnimeDTO(
                reference=ExternalReferenceDTO(
                    provider_id="animeflv", external_id="example-anime"
                ),
                title="Example Anime",
                synopsis="Una sinopsis de ejemplo.",
                genres=("Comedia",),
            ),
            episodes=[
                ProviderEpisodeDTO(
                    reference=ExternalReferenceDTO(
                        provider_id="animeflv", external_id="example-anime:1"
                    ),
                    number=1,
                    title="Example Anime Episodio 1",
                    sources=(
                        ProviderSourceDTO(
                            url="https://mega.nz/file/example",
                            quality="MP4",
                            subtitle_language_code="es",
                        ),
                    ),
                )
            ],
        ),
    )
    app.dependency_overrides[deps.get_catalog_unit_of_work] = lambda: uow
    app.dependency_overrides[deps.get_provider_manager] = lambda: manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


class TestIngestAnimeEndpoint:
    async def test_ingests_and_returns_full_detail(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/anime/external/animeflv/example-anime")

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Example Anime"
        assert body["synopsis"] == "Una sinopsis de ejemplo."
        assert len(body["seasons"]) == 1
        assert len(body["seasons"][0]["episodes"]) == 1
        assert len(body["seasons"][0]["episodes"][0]["streaming_sources"]) == 1

    async def test_second_call_returns_same_internal_id(self, client: AsyncClient) -> None:
        first = await client.get("/api/v1/anime/external/animeflv/example-anime")
        second = await client.get("/api/v1/anime/external/animeflv/example-anime")

        assert first.json()["id"] == second.json()["id"]

    async def test_ingested_anime_is_reachable_by_internal_id(
        self, client: AsyncClient
    ) -> None:
        ingested = await client.get("/api/v1/anime/external/animeflv/example-anime")
        anime_id = ingested.json()["id"]

        response = await client.get(f"/api/v1/anime/{anime_id}")

        assert response.status_code == 200
        assert response.json()["title"] == "Example Anime"

    async def test_returns_404_when_provider_has_no_such_anime(
        self, client: AsyncClient
    ) -> None:
        empty_manager = ProviderManager()
        empty_manager.register(PROVIDER_ID, FakeProviderPort(anime_detail=None))
        app.dependency_overrides[deps.get_provider_manager] = lambda: empty_manager

        response = await client.get("/api/v1/anime/external/animeflv/does-not-exist")

        assert response.status_code == 404
