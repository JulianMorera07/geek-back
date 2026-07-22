"""Test de integración de punta a punta: `ProviderFactory` construye el
adapter de AnimeFLV a partir de una `ProviderConfiguration`, se registra
en un `ProviderManager` real (con cache y retry reales, no dobles), y se
ejercita una llamada completa con HTTP mockeado por `respx`. Verifica que
el Provider Framework completo (Sprints 4-5) funciona también con un
adapter basado en scraping, no solo con APIs oficiales como Jikan.
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
from geekbaku.infrastructure.providers.animeflv.adapter import create_animeflv_adapter

BASE_URL = "https://animeflv.test"
PROVIDER_ID = ProviderId("animeflv")

EXAMPLE_IMG = "https://animeflv.test/wp-content/uploads/example.jpg"

CATALOG_HTML = f"""
<html><body>
<div class="ht_grid_1_4 post-1 category-example-anime genre-accion">
  <a href="https://animeflv.test/anime/example-anime/">
    <img class="anime-image" src="{EXAMPLE_IMG}" alt="Example Anime">
    <h2 class="entry-title">Example Anime</h2>
  </a>
</div>
</body></html>
"""


def make_manager_with_animeflv(**manager_kwargs: object) -> ProviderManager:
    factory = ProviderFactory()
    factory.register_constructor("animeflv", create_animeflv_adapter)

    configuration = ProviderConfiguration(provider_id=PROVIDER_ID, base_url=BASE_URL)
    adapter = factory.create("animeflv", configuration)

    manager = ProviderManager(**manager_kwargs)  # type: ignore[arg-type]
    manager.register(PROVIDER_ID, adapter, configuration=configuration)
    return manager


class TestFactoryToManagerIntegration:
    @respx.mock
    async def test_get_popular_through_manager_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, text=CATALOG_HTML))
        manager = make_manager_with_animeflv()

        results = await manager.get_popular(Pagination())

        assert len(results) == 1
        assert results[0].title == "Example Anime"

    @respx.mock
    async def test_get_genres_is_cached_by_manager(self) -> None:
        route = respx.get(f"{BASE_URL}/", params={"anime_page": 1}).mock(
            return_value=httpx.Response(200, text=CATALOG_HTML)
        )
        manager = make_manager_with_animeflv(cache=InMemoryProviderCache())

        first = await manager.get_genres(PROVIDER_ID)
        second = await manager.get_genres(PROVIDER_ID)

        assert first == second == ["Accion"]
        assert route.call_count == 1  # la segunda llamada vino de cache

    @respx.mock
    async def test_health_reflects_successful_call(self) -> None:
        respx.get(f"{BASE_URL}/", params={"anime_page": 1}).mock(
            return_value=httpx.Response(200, text=CATALOG_HTML)
        )
        manager = make_manager_with_animeflv()

        await manager.get_genres(PROVIDER_ID)

        assert manager.get_health(PROVIDER_ID).status == ProviderStatus.HEALTHY

    @respx.mock
    async def test_transient_failure_is_retried_and_recovers(self) -> None:
        route = respx.get(f"{BASE_URL}/", params={"anime_page": 1})
        route.side_effect = [httpx.Response(500), httpx.Response(200, text=CATALOG_HTML)]

        async def no_sleep(_seconds: float) -> None:
            return None

        manager = make_manager_with_animeflv(retry_policy=RetryPolicy(sleep=no_sleep))

        genres = await manager.get_genres(PROVIDER_ID)

        assert genres == ["Accion"]
        assert manager.get_stats(PROVIDER_ID).retried_calls == 1
