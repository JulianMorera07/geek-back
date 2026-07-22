"""Tests de integración de `AnimeFlvProviderAdapter`.

Usan `respx` para interceptar las peticiones HTTP en el nivel de
transporte de `httpx` (nunca hay red real), con fixtures HTML sintéticas
que reproducen la ESTRUCTURA observada del sitio con datos ficticios —
verifican en conjunto: construcción de URL/params, parsing HTML y mapeo a
los DTOs de GeekBaku, sin depender de que animeflv.or.at esté disponible
ni de que su markup no haya cambiado desde que se escribió el adapter.
"""

import httpx
import respx

from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId
from geekbaku.infrastructure.providers.animeflv.adapter import AnimeFlvProviderAdapter
from geekbaku.infrastructure.providers.animeflv.client import AnimeFlvClient

BASE_URL = "https://animeflv.test"
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

SEARCH_HTML = f"""
<html><body>
<div class="search-series-grid">
  <div class="search-series-card 1">
    <a class="thumbnail-link" href="https://animeflv.test/anime/example-anime/">
      <img class="anime-image" src="{EXAMPLE_IMG}" alt="Example Anime">
      <h2 class="entry-title">Example Anime</h2>
    </a>
  </div>
</div>
</body></html>
"""

LATEST_HTML = f"""
<html><body>
<div class="home-recent-episodes">
  <a href="https://animeflv.test/2026/07/20/example-anime-episodio-3/"
     title="Example Anime Episodio 3">
    <img src="{EXAMPLE_IMG}" alt="Example Anime">
  </a>
</div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1>Example Anime</h1>
<div class="anime-rating"><span class="rating-score">8.5</span></div>
<div class="anime-genres"><span class="genre-tag">Comedia</span></div>
<div class="anime-synopsis"><h3>Sinopsis</h3><p>Sinopsis de ejemplo.</p></div>
<script type="application/json" class="animeflv-episodes-data">
[{"post_id": 1,
  "permalink": "https://animeflv.test/2026/07/13/example-anime-episodio-1/",
  "number": 1, "range": 1}]
</script>
</body></html>
"""

EPISODE_HTML = """
<html><body>
<h1>Example Anime Episodio 1 Sub Español</h1>
<div class="download-link">
  <table class="styled-table">
    <tbody>
      <tr><td>Mega</td><td>MP4</td><td>SUB</td><td><a href="https://mega.nz/file/example">Descargar</a></td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""


def make_adapter() -> AnimeFlvProviderAdapter:
    http_client = httpx.AsyncClient()
    return AnimeFlvProviderAdapter(AnimeFlvClient(http_client, base_url=BASE_URL))


REFERENCE = ExternalReference(provider_id=ProviderId("animeflv"), external_id="example-anime")


class TestSearch:
    @respx.mock
    async def test_returns_normalized_results(self) -> None:
        respx.get(f"{BASE_URL}/", params={"s": "example"}).mock(
            return_value=httpx.Response(200, text=SEARCH_HTML)
        )
        adapter = make_adapter()

        results = await adapter.search("example", Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].provider_id == "animeflv"
        assert results[0].external_id == "example-anime"
        assert results[0].title == "Example Anime"

    @respx.mock
    async def test_paginates_client_side(self) -> None:
        respx.get(f"{BASE_URL}/", params={"s": "example"}).mock(
            return_value=httpx.Response(200, text=SEARCH_HTML)
        )
        adapter = make_adapter()

        results = await adapter.search("example", Pagination(page=2, page_size=20))

        assert results == []


class TestGetAnimeDetail:
    @respx.mock
    async def test_returns_mapped_detail(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime/").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        adapter = make_adapter()

        detail = await adapter.get_anime_detail(REFERENCE)

        assert detail is not None
        assert detail.title == "Example Anime"
        assert detail.rating_score == 8.5
        assert detail.genres == ("Comedia",)

    @respx.mock
    async def test_returns_none_on_404(self) -> None:
        respx.get(f"{BASE_URL}/anime/does-not-exist/").mock(return_value=httpx.Response(404))
        adapter = make_adapter()

        result = await adapter.get_anime_detail(
            ExternalReference(provider_id=ProviderId("animeflv"), external_id="does-not-exist")
        )

        assert result is None


class TestGetEpisodes:
    @respx.mock
    async def test_fetches_episode_list_and_sources(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime/").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        respx.get("https://animeflv.test/2026/07/13/example-anime-episodio-1/").mock(
            return_value=httpx.Response(200, text=EPISODE_HTML)
        )
        adapter = make_adapter()

        episodes = await adapter.get_episodes(REFERENCE)

        assert len(episodes) == 1
        assert episodes[0].number == 1
        assert episodes[0].sources[0].label == "Mega"
        assert episodes[0].sources[0].url == "https://mega.nz/file/example"


class TestGetSeasons:
    @respx.mock
    async def test_returns_single_pseudo_season(self) -> None:
        respx.get(f"{BASE_URL}/anime/example-anime/").mock(
            return_value=httpx.Response(200, text=DETAIL_HTML)
        )
        adapter = make_adapter()

        seasons = await adapter.get_seasons(REFERENCE)

        assert len(seasons) == 1
        assert seasons[0].number == 1
        assert seasons[0].episode_count == 1


class TestGetRelated:
    async def test_always_returns_empty_list(self) -> None:
        adapter = make_adapter()

        related = await adapter.get_related(REFERENCE)

        assert related == []


class TestGetLatest:
    @respx.mock
    async def test_returns_animes_derived_from_episode_links(self) -> None:
        respx.get(f"{BASE_URL}/", params={"episodes_page": 1}).mock(
            return_value=httpx.Response(200, text=LATEST_HTML)
        )
        adapter = make_adapter()

        results = await adapter.get_latest(Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].external_id == "example-anime"


class TestGetPopular:
    @respx.mock
    async def test_uses_home_airing_section_as_proxy(self) -> None:
        respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, text=CATALOG_HTML))
        adapter = make_adapter()

        results = await adapter.get_popular(Pagination(page=1, page_size=20))

        assert len(results) == 1
        assert results[0].external_id == "example-anime"


class TestGetGenres:
    @respx.mock
    async def test_returns_genres_seen_in_catalog(self) -> None:
        respx.get(f"{BASE_URL}/", params={"anime_page": 1}).mock(
            return_value=httpx.Response(200, text=CATALOG_HTML)
        )
        adapter = make_adapter()

        genres = await adapter.get_genres()

        assert genres == ["Accion"]


class TestGetTypes:
    async def test_returns_static_types(self) -> None:
        adapter = make_adapter()

        types = await adapter.get_types()

        assert "TV" in types
