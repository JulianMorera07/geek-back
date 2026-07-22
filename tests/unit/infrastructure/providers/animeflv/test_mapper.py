"""Tests unitarios puros de `mapper.py`: HTML crudo (fixtures sintéticas,
sin HTTP) -> DTOs de GeekBaku. Los fixtures reproducen la ESTRUCTURA
observada del sitio (clases CSS, JSON embebido) con datos ficticios, no
contenido real scrapeado. Ver `test_adapter.py` (integración, con
`respx`) para el flujo completo con HTTP mockeado.
"""

from geekbaku.infrastructure.providers.animeflv.mapper import (
    PROVIDER_ID,
    STATIC_ANIME_TYPES,
    build_pseudo_season,
    parse_anime_detail,
    parse_episode_page,
    parse_episode_refs,
    parse_genre_names,
    parse_latest_episode_items,
    parse_listing_items,
    parse_search_results,
    to_external_reference,
)

EXAMPLE_IMG = "https://animeflv.or.at/wp-content/uploads/example.jpg"
SECOND_IMG = "https://animeflv.or.at/wp-content/uploads/second.jpg"

CATALOG_GRID_HTML = f"""
<html><body>
<div class="ht_grid_1_4 post-1 category-example-anime genre-accion genre-comedia">
  <a href="https://animeflv.or.at/anime/example-anime/">
    <div class="thumbnail-wrap">
      <img class="anime-image" src="{EXAMPLE_IMG}" alt="Example Anime">
      <span class="Estreno"><span>ESTRENO</span></span>
    </div>
    <h2 class="entry-title">Example Anime</h2>
  </a>
</div>
<div class="ht_grid_1_4 post-2 category-second-anime genre-drama">
  <a href="https://animeflv.or.at/anime/second-anime/">
    <img class="anime-image" src="{SECOND_IMG}" alt="Second Anime">
    <h2 class="entry-title">Second Anime</h2>
  </a>
</div>
</body></html>
"""

SEARCH_RESULTS_HTML = f"""
<html><body>
<div class="search-series-grid">
  <div class="search-series-card 1">
    <a class="thumbnail-link" href="https://animeflv.or.at/anime/example-anime/">
      <div class="thumbnail-wrap">
        <img class="anime-image" src="{EXAMPLE_IMG}" alt="Example Anime">
      </div>
      <h2 class="entry-title">Example Anime</h2>
    </a>
  </div>
</div>
</body></html>
"""

LATEST_EPISODES_HTML = f"""
<html><body>
<div class="home-recent-episodes">
  <a href="https://animeflv.or.at/2026/07/20/example-anime-episodio-3/"
     title="Example Anime Episodio 3">
    <img src="{EXAMPLE_IMG}" alt="Example Anime">
  </a>
</div>
</body></html>
"""

ANIME_DETAIL_HTML = f"""
<html><body>
<h1>Example Anime</h1>
<div class="anime-poster"><img class="poster-image" src="{EXAMPLE_IMG}"></div>
<div class="anime-rating"><span class="rating-score">8.72</span></div>
<div class="anime-genres">
  <span class="genre-tag">Comedia</span>
  <span class="genre-tag">Seinen</span>
</div>
<div class="anime-synopsis"><h3>Sinopsis</h3><p>Una sinopsis de ejemplo para tests.</p></div>
<script type="application/json" class="animeflv-episodes-data">
[{{"post_id": 2, "permalink": "https://animeflv.or.at/2026/07/20/example-anime-episodio-2/",
   "number": 2, "range": 1}},
 {{"post_id": 1, "permalink": "https://animeflv.or.at/2026/07/13/example-anime-episodio-1/",
   "number": 1, "range": 1}}]
</script>
</body></html>
"""

ANIME_DETAIL_WITHOUT_EPISODES_HTML = """
<html><body><h1>Example Anime</h1></body></html>
"""

EPISODE_PAGE_HTML = """
<html><body>
<h1>Example Anime Episodio 1 Sub Español</h1>
<div class="download-link">
  <table class="styled-table">
    <thead><tr><th>SERVIDOR</th><th>FORMATO</th><th>IDIOMA</th><th>DESCARGAR</th></tr></thead>
    <tbody>
      <tr><td>Mega</td><td>MP4</td><td>SUB</td><td><a href="https://mega.nz/file/example">Descargar</a></td></tr>
      <tr><td>MP4Upload</td><td>MP4</td><td>LAT</td><td><a href="https://www.mp4upload.com/example">Descargar</a></td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""


class TestParseListingItems:
    def test_extracts_slug_title_and_thumbnail(self) -> None:
        items = parse_listing_items(CATALOG_GRID_HTML)

        assert len(items) == 2
        first = items[0]
        assert first.provider_id == PROVIDER_ID
        assert first.external_id == "example-anime"
        assert first.title == "Example Anime"
        assert first.thumbnail_url == "https://animeflv.or.at/wp-content/uploads/example.jpg"

    def test_title_does_not_include_estreno_badge(self) -> None:
        items = parse_listing_items(CATALOG_GRID_HTML)

        assert items[0].title == "Example Anime"
        assert "ESTRENO" not in items[0].title

    def test_deduplicates_by_slug(self) -> None:
        html = CATALOG_GRID_HTML + CATALOG_GRID_HTML
        items = parse_listing_items(html)

        assert len(items) == 2


class TestParseSearchResults:
    def test_extracts_result_from_search_grid(self) -> None:
        items = parse_search_results(SEARCH_RESULTS_HTML)

        assert len(items) == 1
        assert items[0].external_id == "example-anime"
        assert items[0].title == "Example Anime"

    def test_returns_empty_list_when_no_results(self) -> None:
        html = "<html><body><div class='search-series-grid'></div></body></html>"

        items = parse_search_results(html)

        assert items == []


class TestParseLatestEpisodeItems:
    def test_derives_anime_from_episode_url(self) -> None:
        items = parse_latest_episode_items(LATEST_EPISODES_HTML)

        assert len(items) == 1
        assert items[0].external_id == "example-anime"
        assert items[0].title == "Example Anime"


class TestParseGenreNames:
    def test_aggregates_distinct_genre_classes(self) -> None:
        genres = parse_genre_names(CATALOG_GRID_HTML)

        assert genres == ["Accion", "Comedia", "Drama"]


class TestParseAnimeDetail:
    def test_extracts_all_fields(self) -> None:
        detail = parse_anime_detail(ANIME_DETAIL_HTML, "example-anime")

        assert detail.reference.provider_id == PROVIDER_ID
        assert detail.reference.external_id == "example-anime"
        assert detail.title == "Example Anime"
        assert detail.synopsis == "Una sinopsis de ejemplo para tests."
        assert detail.genres == ("Comedia", "Seinen")
        assert detail.rating_score == 8.72
        assert detail.thumbnail_url == "https://animeflv.or.at/wp-content/uploads/example.jpg"

    def test_missing_fields_default_to_none(self) -> None:
        detail = parse_anime_detail(ANIME_DETAIL_WITHOUT_EPISODES_HTML, "example-anime")

        assert detail.synopsis is None
        assert detail.genres == ()
        assert detail.rating_score is None
        assert detail.thumbnail_url is None


class TestParseEpisodeRefs:
    def test_parses_embedded_json_script(self) -> None:
        refs = parse_episode_refs(ANIME_DETAIL_HTML)

        assert len(refs) == 2
        assert {ref["number"] for ref in refs} == {1, 2}
        assert refs[0]["permalink"].startswith("https://animeflv.or.at/")

    def test_returns_empty_list_when_script_missing(self) -> None:
        assert parse_episode_refs(ANIME_DETAIL_WITHOUT_EPISODES_HTML) == []

    def test_returns_empty_list_for_malformed_json(self) -> None:
        html = '<script class="animeflv-episodes-data">not json</script>'
        assert parse_episode_refs(html) == []


class TestParseEpisodePage:
    def test_extracts_title_and_sources(self) -> None:
        episode = parse_episode_page(EPISODE_PAGE_HTML, "example-anime", 1, 1)

        assert episode.reference.external_id == "example-anime:1"
        assert episode.number == 1
        assert episode.title == "Example Anime Episodio 1 Sub Español"
        assert len(episode.sources) == 2

        mega = episode.sources[0]
        assert mega.label == "Mega"
        assert mega.url == "https://mega.nz/file/example"
        assert mega.subtitle_language_code == "es"

        mp4upload = episode.sources[1]
        assert mp4upload.subtitle_language_code is None

    def test_returns_no_sources_when_table_missing(self) -> None:
        episode = parse_episode_page("<html><body><h1>Title</h1></body></html>", "slug", 1, 1)

        assert episode.sources == ()
        assert episode.title == "Title"


class TestBuildPseudoSeason:
    def test_returns_single_season_with_episode_count(self) -> None:
        reference = to_external_reference("example-anime")

        season = build_pseudo_season(reference, "Example Anime", 12)

        assert season.number == 1
        assert season.title == "Example Anime"
        assert season.episode_count == 12


def test_static_anime_types_is_non_empty() -> None:
    assert len(STATIC_ANIME_TYPES) > 0


def test_to_external_reference() -> None:
    reference = to_external_reference("example-anime")
    assert reference.provider_id == PROVIDER_ID
    assert reference.external_id == "example-anime"
