"""Test de integración del Aggregation Engine con MÚLTIPLES proveedores
reales/mockeados a la vez: el adapter real de Jikan (HTTP mockeado con
`respx`, sin red real) + un segundo `FakeProviderPort` registrados juntos en
el mismo `ProviderManager`. Verifica que el pipeline completo (Provider
Framework → Aggregation Engine: dedup → merge → rank → cache) funciona de
punta a punta cuando dos proveedores DISTINTOS reportan el mismo anime.
"""

import httpx
import respx

from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import InMemoryProviderCache
from geekbaku.application.providers.dto import SearchResultDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import ProviderId
from geekbaku.infrastructure.providers.jikan.adapter import JikanProviderAdapter
from geekbaku.infrastructure.providers.jikan.client import JikanClient
from tests.unit.application.providers.fakes import FakeProviderPort

JIKAN_BASE_URL = "https://api.jikan.moe/v4"
JIKAN_PROVIDER_ID = ProviderId("jikan")
FAKE_PROVIDER_ID = ProviderId("fake-provider")


def make_manager() -> ProviderManager:
    manager = ProviderManager()
    jikan_client = JikanClient(httpx.AsyncClient(), base_url=JIKAN_BASE_URL)
    manager.register(JIKAN_PROVIDER_ID, JikanProviderAdapter(jikan_client), priority=10)
    manager.register(
        FAKE_PROVIDER_ID,
        FakeProviderPort(
            search_results=[
                SearchResultDTO(
                    provider_id=str(FAKE_PROVIDER_ID),
                    external_id="local-1",
                    title="Shingeki no Kyojin",
                    thumbnail_url="https://cdn.fake-provider.example/aot.jpg",
                )
            ]
        ),
        priority=1,
    )
    return manager


class TestMultiProviderSearchAggregation:
    @respx.mock
    async def test_deduplicates_the_same_anime_reported_by_two_providers(self) -> None:
        respx.get(f"{JIKAN_BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "mal_id": 16498,
                            "title": "Shingeki no Kyojin",
                            "type": "TV",
                            "year": 2013,
                        }
                    ]
                },
            )
        )
        engine = AggregationEngine(manager=make_manager())

        results = await engine.search("shingeki no kyojin")

        assert len(results) == 1
        merged = results[0]
        assert {s.provider_id for s in merged.sources} == {"jikan", "fake-provider"}
        # el provider de mayor prioridad (jikan) gana el título/tipo/año,
        # pero el thumbnail lo aporta el otro provider (jikan no trajo uno
        # en este fixture) — así se ve que realmente se fusionó información.
        assert merged.anime_type == "TV"
        assert merged.thumbnail_url == "https://cdn.fake-provider.example/aot.jpg"

    @respx.mock
    async def test_keeps_unrelated_results_separate(self) -> None:
        respx.get(f"{JIKAN_BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"mal_id": 1, "title": "One Piece", "type": "TV", "year": 1999}]},
            )
        )
        engine = AggregationEngine(manager=make_manager())

        results = await engine.search("anime")

        assert len(results) == 2
        assert {r.title for r in results} == {"One Piece", "Shingeki no Kyojin"}

    @respx.mock
    async def test_ranks_by_provider_priority_when_not_merged(self) -> None:
        respx.get(f"{JIKAN_BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"mal_id": 1, "title": "One Piece", "type": "TV", "year": 1999}]},
            )
        )
        engine = AggregationEngine(manager=make_manager())

        results = await engine.search("anime")

        # jikan (prioridad 10) debería listarse antes que fake-provider (prioridad 1)
        provider_ids = [s.provider_id for r in results for s in r.sources]
        assert provider_ids.index("jikan") < provider_ids.index("fake-provider")

    @respx.mock
    async def test_aggregated_cache_avoids_a_second_round_of_http_calls(self) -> None:
        route = respx.get(f"{JIKAN_BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"mal_id": 16498, "title": "Shingeki no Kyojin", "type": "TV", "year": 2013}
                    ]
                },
            )
        )
        engine = AggregationEngine(manager=make_manager(), cache=InMemoryProviderCache())
        pagination = Pagination()

        await engine.search("shingeki no kyojin", pagination)
        await engine.search("shingeki no kyojin", pagination)

        assert route.call_count == 1
