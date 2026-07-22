"""Tests de integración de `TioAnimeProviderAdapter`.

Usan `respx` para interceptar las peticiones HTTP en el nivel de
transporte de `httpx` (nunca hay red real), con fixtures HTML/JSON
sintéticas que reproducen la ESTRUCTURA observada del sitio con datos
ficticios.
"""

import httpx
import respx

from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId
from geekbaku.infrastructure.providers.tioanime.adapter import TioAnimeProviderAdapter
from geekbaku.infrastructure.providers.tioanime.client import TioAnimeClient

BASE_URL = "https://tioanime.test"

SEARCH_JSON = [{"id": "1", "title": "Example Anime", "slug": "example-anime", "type": "0"}]

DIRECTORY_HTML = """
<html><body>
<article class="anime">
  <a href="/anime/example-anime">
    <div class="thumb"><img src="/uploads/portadas/1.jpg" alt="Example Anime"></div>
    <h3 class="title">Example Anime</h3>
  </a>
</article>
</body></html>
"""

LATEST_HTML = """
<html><body>
<article class="episode">
  <a href="/ver/example-anime-3">
    <div class="thumb"><img src="/uploads/thumbs/1.jpg" alt="Example Anime 3"></div>
    <h3 class="title">Example Anime 3</h3>
  </a>
</article>
</body></html>
"""

GENRE_HTML = """
<html><body>
<select id="genero" name="genero[]" multiple>
  <option value="comedia">Comedia</option>
  <option value="hentai">Hentai</option>
</select>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1 class="title">Example Anime</h1>
<a class="btn btn-success btn-block status">Finalizado</a>
<p class="genres"><a href="/directorio?genero=comedia">Comedia</a></p>
<p class="sinopsis">Sinopsis de ejemplo.</p>
<script>
    var anime_info = ["1","example-anime","Example Anime","2026-07-29"];
    var episodes = [1];
</script>
</body></html>
"""

DETAIL_HTML_ADULT = """
<html><body>
<h1 class="title">Adult Example</h1>
<p class="genres"><a href="/directorio?genero=hentai">Hentai</a></p>
<script>
    var episodes = [1];
</script>
</body></html>
"""

EPISODE_HTML = """
<html><body>
<script>
    var videos = [["Mega","https://mega.nz/embed/example",0,0]];
</script>
</body></html>
"""


def make_adapter() -> TioAnimeProviderAdapter:
    http_client = httpx.AsyncClient()
    return TioAnimeProviderAdapter(TioAnimeClient(http_client, base_url=BASE_URL))


REFERENCE = ExternalReference(provider_id=ProviderId("tioanime"), external_id="example-anime")


class TestSearch:
    @respx.mock
    async def test_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/api/search", params={"value": "example"}).mock(
            return_value=httpx.Response(200, json=SEARCH_JSON)
        )
        adapter = make_adapter()

        results = await adapter.search("example", Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].provider_id == "tioanime"
        assert results[0].external_id == "example-anime"


class TestGetAnimeDetail:
    @respx.mock
    async def test_returns_mapped_detail(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        adapter = make_adapter()

        detail = await adapter.get_anime_detail(REFERENCE)

        assert detail is not None
        assert detail.title == "Example Anime"
        assert detail.genres == ("Comedia",)

    @respx.mock
    async def test_returns_none_on_404(self) -> None:
        respx.get(f"{BASE_URL}/anime/does-not-exist").mock(return_value=httpx.Response(404))
        adapter = make_adapter()

        result = await adapter.get_anime_detail(
            ExternalReference(provider_id=ProviderId("tioanime"), external_id="does-not-exist")
        )

        assert result is None

    @respx.mock
    async def test_returns_none_for_adult_tagged_content(self) -> None:
        """Defensa en profundidad: si alguna vez el sitio taggeara un
        anime con un género de contenido adulto, el adapter lo trata como
        inexistente en vez de servirlo."""
        respx.get(f"{BASE_URL}/anime/adult-example").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML_ADULT)
        )
        adapter = make_adapter()

        result = await adapter.get_anime_detail(
            ExternalReference(provider_id=ProviderId("tioanime"), external_id="adult-example")
        )

        assert result is None


class TestGetEpisodes:
    @respx.mock
    async def test_fetches_episode_list_and_sources(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        respx.get(f"{BASE_URL}/ver/example-anime-1").mock(
            return_value=httpx.Response(200, text=EPISODE_HTML)
        )
        adapter = make_adapter()

        episodes = await adapter.get_episodes(REFERENCE)

        assert len(episodes) == 1
        assert episodes[0].number == 1
        assert episodes[0].sources[0].label == "Mega"
        assert episodes[0].sources[0].url == "https://mega.nz/embed/example"


class TestGetSeasons:
    @respx.mock
    async def test_returns_single_pseudo_season(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        adapter = make_adapter()

        seasons = await adapter.get_seasons(REFERENCE)

        assert len(seasons) == 1
        assert seasons[0].episode_count == 1


class TestGetRelated:
    async def test_always_returns_empty_list(self) -> None:
        adapter = make_adapter()

        related = await adapter.get_related(REFERENCE)

        assert related == []


class TestGetLatest:
    @respx.mock
    async def test_returns_animes_derived_from_episode_links(self) -> None:
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, text=LATEST_HTML))
        adapter = make_adapter()

        results = await adapter.get_latest(Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].external_id == "example-anime"


class TestGetPopular:
    @respx.mock
    async def test_uses_home_directory_section_as_proxy(self) -> None:
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, text=DIRECTORY_HTML))
        adapter = make_adapter()

        results = await adapter.get_popular(Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].external_id == "example-anime"


class TestGetGenres:
    @respx.mock
    async def test_excludes_adult_genres(self) -> None:
        respx.get(f"{BASE_URL}/directorio", params={"p": 1}).mock(
            return_value=httpx.Response(200, text=GENRE_HTML)
        )
        adapter = make_adapter()

        genres = await adapter.get_genres()

        assert genres == ["Comedia"]
        assert "Hentai" not in genres


class TestGetTypes:
    async def test_returns_static_types(self) -> None:
        adapter = make_adapter()

        types = await adapter.get_types()

        assert "TV" in types
