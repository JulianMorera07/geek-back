"""Test de integración de punta a punta: `ProviderFactory` construye el
adapter de Jikan a partir de una `ProviderConfiguration`, se registra en un
`ProviderManager` real (con cache y retry reales, no dobles), y se ejercita
una llamada completa con HTTP mockeado por `respx`. Verifica que el
Provider Framework completo (Sprint 4 + 5) funciona con un adapter real, no
solo con los `FakeProviderPort` usados en los tests unitarios del Manager.
"""

import httpx
import respx

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import InMemoryProviderCache
from geekbaku.application.providers.factory import ProviderFactory
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.retry import RetryPolicy
from geekbaku.domain.providers.value_objects import (
    ProviderConfiguration,
    ProviderId,
    ProviderStatus,
)
from geekbaku.infrastructure.providers.jikan.adapter import create_jikan_adapter

BASE_URL = "https://api.jikan.moe/v4"
PROVIDER_ID = ProviderId("jikan")


def make_manager_with_jikan(**manager_kwargs: object) -> ProviderManager:
    factory = ProviderFactory()
    factory.register_constructor("jikan", create_jikan_adapter)

    configuration = ProviderConfiguration(provider_id=PROVIDER_ID, base_url=BASE_URL)
    adapter = factory.create("jikan", configuration)

    manager = ProviderManager(**manager_kwargs)  # type: ignore[arg-type]
    manager.register(PROVIDER_ID, adapter, configuration=configuration)
    return manager


class TestFactoryToManagerIntegration:
    @respx.mock
    async def test_search_through_manager_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/anime").mock(
            return_value=httpx.Response(
                200, json={"data": [{"mal_id": 1, "title": "Frieren", "type": "TV"}]}
            )
        )
        manager = make_manager_with_jikan()

        results = await manager.search("frieren", Pagination())

        assert len(results) == 1
        assert results[0].title == "Frieren"

    @respx.mock
    async def test_get_genres_is_cached_by_manager(self) -> None:
        route = respx.get(f"{BASE_URL}/genres/anime").mock(
            return_value=httpx.Response(200, json={"data": [{"mal_id": 1, "name": "Action"}]})
        )
        manager = make_manager_with_jikan(cache=InMemoryProviderCache())

        first = await manager.get_genres(PROVIDER_ID)
        second = await manager.get_genres(PROVIDER_ID)

        assert first == second == ["Action"]
        assert route.call_count == 1  # la segunda llamada vino de cache

    @respx.mock
    async def test_health_reflects_successful_call(self) -> None:
        respx.get(f"{BASE_URL}/genres/anime").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        manager = make_manager_with_jikan()

        await manager.get_genres(PROVIDER_ID)

        assert manager.get_health(PROVIDER_ID).status == ProviderStatus.HEALTHY

    @respx.mock
    async def test_transient_failure_is_retried_and_recovers(self) -> None:
        route = respx.get(f"{BASE_URL}/genres/anime")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json={"data": [{"mal_id": 1, "name": "Action"}]}),
        ]

        async def no_sleep(_seconds: float) -> None:
            return None

        manager = make_manager_with_jikan(retry_policy=RetryPolicy(sleep=no_sleep))

        genres = await manager.get_genres(PROVIDER_ID)

        assert genres == ["Action"]
        assert manager.get_stats(PROVIDER_ID).retried_calls == 1
