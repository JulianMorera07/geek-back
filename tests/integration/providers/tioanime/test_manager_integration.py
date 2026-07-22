"""Test de integración de punta a punta: `ProviderFactory` construye el
adapter de TioAnime a partir de una `ProviderConfiguration`, se registra
en un `ProviderManager` real (con cache y retry reales, no dobles), y se
ejercita una llamada completa con HTTP mockeado por `respx`.
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
from geekbaku.infrastructure.providers.tioanime.adapter import create_tioanime_adapter

BASE_URL = "https://tioanime.test"
PROVIDER_ID = ProviderId("tioanime")

GENRE_HTML = """
<html><body>
<select id="genero" name="genero[]" multiple>
  <option value="comedia">Comedia</option>
</select>
</body></html>
"""

DIRECTORY_HTML = """
<html><body>
<article class="anime">
  <a href="/anime/example-anime">
    <img src="/uploads/portadas/1.jpg" alt="Example Anime">
    <h3 class="title">Example Anime</h3>
  </a>
</article>
</body></html>
"""


def make_manager_with_tioanime(**manager_kwargs: object) -> ProviderManager:
    factory = ProviderFactory()
    factory.register_constructor("tioanime", create_tioanime_adapter)

    configuration = ProviderConfiguration(provider_id=PROVIDER_ID, base_url=BASE_URL)
    adapter = factory.create("tioanime", configuration)

    manager = ProviderManager(**manager_kwargs)  # type: ignore[arg-type]
    manager.register(PROVIDER_ID, adapter, configuration=configuration)
    return manager


class TestFactoryToManagerIntegration:
    @respx.mock
    async def test_get_popular_through_manager_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, text=DIRECTORY_HTML))
        manager = make_manager_with_tioanime()

        results = await manager.get_popular(Pagination())

        assert len(results) == 1
        assert results[0].title == "Example Anime"

    @respx.mock
    async def test_get_genres_is_cached_by_manager(self) -> None:
        route = respx.get(f"{BASE_URL}/directorio", params={"p": 1}).mock(
            return_value=httpx.Response(200, text=GENRE_HTML)
        )
        manager = make_manager_with_tioanime(cache=InMemoryProviderCache())

        first = await manager.get_genres(PROVIDER_ID)
        second = await manager.get_genres(PROVIDER_ID)

        assert first == second == ["Comedia"]
        assert route.call_count == 1  # la segunda llamada vino de cache

    @respx.mock
    async def test_health_reflects_successful_call(self) -> None:
        respx.get(f"{BASE_URL}/directorio", params={"p": 1}).mock(
            return_value=httpx.Response(200, text=GENRE_HTML)
        )
        manager = make_manager_with_tioanime()

        await manager.get_genres(PROVIDER_ID)

        assert manager.get_health(PROVIDER_ID).status == ProviderStatus.HEALTHY

    @respx.mock
    async def test_transient_failure_is_retried_and_recovers(self) -> None:
        route = respx.get(f"{BASE_URL}/directorio", params={"p": 1})
        route.side_effect = [httpx.Response(500), httpx.Response(200, text=GENRE_HTML)]

        async def no_sleep(_seconds: float) -> None:
            return None

        manager = make_manager_with_tioanime(retry_policy=RetryPolicy(sleep=no_sleep))

        genres = await manager.get_genres(PROVIDER_ID)

        assert genres == ["Comedia"]
        assert manager.get_stats(PROVIDER_ID).retried_calls == 1
