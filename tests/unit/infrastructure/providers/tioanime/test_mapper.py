"""Tests unitarios puros de `mapper.py`: HTML/JSON crudo (fixtures
sintéticas, sin HTTP) -> DTOs de GeekBaku. Los fixtures reproducen la
ESTRUCTURA observada del sitio (clases CSS, variables JS embebidas) con
datos ficticios, no contenido real scrapeado.
"""

from geekbaku.infrastructure.providers.tioanime.mapper import (
    PROVIDER_ID,
    STATIC_ANIME_TYPES,
    build_pseudo_season,
    is_adult_genre,
    parse_anime_detail,
    parse_directory_items,
    parse_episode_numbers,
    parse_episode_page,
    parse_genre_names,
    parse_latest_episode_items,
    parse_search_results,
    to_external_reference,
)

SEARCH_JSON = [
    {"id": "1", "title": "Example Anime", "slug": "example-anime", "type": "0"},
    {"id": "2", "title": "Example Anime Movie", "slug": "example-anime-movie", "type": "1"},
    {"id": "3", "title": "No Slug", "type": "0"},
]

DIRECTORY_HTML = """
<html><body>
<article class="anime">
  <a href="/anime/example-anime">
    <div class="thumb"><img src="/uploads/portadas/1.jpg" alt="Example Anime"></div>
    <h3 class="title">Example Anime</h3>
  </a>
</article>
<article class="anime">
  <a href="/anime/second-anime">
    <div class="thumb"><img src="/uploads/portadas/2.jpg" alt="Second Anime"></div>
    <h3 class="title">Second Anime</h3>
  </a>
</article>
</body></html>
"""

LATEST_EPISODES_HTML = """
<html><body>
<ul class="episodes list-unstyled row">
<li><article class="episode">
  <a href="/ver/example-anime-3">
    <div class="thumb"><img src="/uploads/thumbs/1.jpg" alt="Example Anime 3"></div>
    <h3 class="title">Example Anime 3</h3>
  </a>
</article></li>
</ul>
</body></html>
"""

GENRE_SELECT_HTML = """
<html><body>
<select id="genero" name="genero[]" multiple>
  <option value="accion">Accion</option>
  <option value="comedia">Comedia</option>
  <option value="hentai">Hentai</option>
</select>
</body></html>
"""

ANIME_DETAIL_HTML = """
<html><body>
<h1 class="title">Example Anime</h1>
<div class="meta">
  <span class="anime-type-tv">TV</span>
  <span class="year">2026</span>
</div>
<a class="btn btn-success btn-block status">Finalizado</a>
<p class="genres">
  <a href="/directorio?genero=comedia">Comedia</a>
  <a href="/directorio?genero=seinen">Seinen</a>
</p>
<div class="anime-single"><img src="/uploads/portadas/1.jpg"></div>
<p class="sinopsis">Una sinopsis de ejemplo para tests.</p>
<script>
    var anime_info = ["1","example-anime","Example Anime","2026-07-29"];
    var episodes = [2,1];
    var episodes_details = ["Hace 1 hora","Hace 7 dias"];
</script>
</body></html>
"""

ANIME_DETAIL_NO_EPISODES_HTML = """
<html><body><h1 class="title">Example Anime</h1></body></html>
"""

EPISODE_PAGE_HTML = """
<html><body>
<script>
    var videos = [["Mega","https://mega.nz/embed/example",0,0],
                   ["YourUpload","https://www.yourupload.com/embed/example",0,0]];
</script>
</body></html>
"""


class TestParseSearchResults:
    def test_maps_valid_items_and_skips_missing_slug(self) -> None:
        results = parse_search_results(SEARCH_JSON)

        assert len(results) == 2
        assert results[0].provider_id == PROVIDER_ID
        assert results[0].external_id == "example-anime"
        assert results[0].title == "Example Anime"
        assert results[0].anime_type == "TV"
        assert results[1].anime_type == "Movie"

    def test_builds_thumbnail_url_from_id(self) -> None:
        """`/api/search` no trae imagen, pero sí `id` — se arma la URL de
        portada con el mismo patrón `/uploads/portadas/{id}.jpg` visto en
        el resto del sitio (verificado contra el sitio real)."""
        results = parse_search_results(SEARCH_JSON)

        assert results[0].thumbnail_url == "https://tioanime.com/uploads/portadas/1.jpg"


class TestParseDirectoryItems:
    def test_extracts_slug_title_and_thumbnail(self) -> None:
        items = parse_directory_items(DIRECTORY_HTML)

        assert len(items) == 2
        assert items[0].external_id == "example-anime"
        assert items[0].title == "Example Anime"
        assert items[0].thumbnail_url == "https://tioanime.com/uploads/portadas/1.jpg"


class TestParseLatestEpisodeItems:
    def test_derives_anime_slug_from_episode_url(self) -> None:
        items = parse_latest_episode_items(LATEST_EPISODES_HTML)

        assert len(items) == 1
        assert items[0].external_id == "example-anime"
        assert items[0].title == "Example Anime 3"


class TestParseGenreNames:
    def test_excludes_adult_genres(self) -> None:
        genres = parse_genre_names(GENRE_SELECT_HTML)

        assert genres == ["Accion", "Comedia"]
        assert "Hentai" not in genres


class TestIsAdultGenre:
    def test_detects_known_keywords(self) -> None:
        assert is_adult_genre("Hentai") is True
        assert is_adult_genre("Contenido Adulto") is True
        assert is_adult_genre("Comedia") is False


class TestParseAnimeDetail:
    def test_extracts_all_fields(self) -> None:
        detail = parse_anime_detail(ANIME_DETAIL_HTML, "example-anime")

        assert detail.title == "Example Anime"
        assert detail.synopsis == "Una sinopsis de ejemplo para tests."
        assert detail.raw_type == "TV"
        assert detail.raw_status == "Finalizado"
        assert detail.genres == ("Comedia", "Seinen")
        assert detail.thumbnail_url == "https://tioanime.com/uploads/portadas/1.jpg"

    def test_missing_fields_default_to_none(self) -> None:
        detail = parse_anime_detail(ANIME_DETAIL_NO_EPISODES_HTML, "example-anime")

        assert detail.synopsis is None
        assert detail.genres == ()
        assert detail.raw_type is None
        assert detail.raw_status is None


class TestParseEpisodeNumbers:
    def test_parses_embedded_js_array(self) -> None:
        numbers = parse_episode_numbers(ANIME_DETAIL_HTML)

        assert numbers == [2, 1]

    def test_returns_empty_list_when_missing(self) -> None:
        assert parse_episode_numbers(ANIME_DETAIL_NO_EPISODES_HTML) == []


class TestParseEpisodePage:
    def test_extracts_embed_sources(self) -> None:
        episode = parse_episode_page(EPISODE_PAGE_HTML, "example-anime", 1)

        assert episode.reference.external_id == "example-anime:1"
        assert episode.number == 1
        assert len(episode.sources) == 2
        assert episode.sources[0].label == "Mega"
        assert episode.sources[0].url == "https://mega.nz/embed/example"

    def test_returns_no_sources_when_missing(self) -> None:
        episode = parse_episode_page("<html><body></body></html>", "slug", 1)

        assert episode.sources == ()


class TestBuildPseudoSeason:
    def test_returns_single_season(self) -> None:
        reference = to_external_reference("example-anime")

        season = build_pseudo_season(reference, "Example Anime", 12)

        assert season.number == 1
        assert season.episode_count == 12


def test_static_anime_types_is_non_empty() -> None:
    assert len(STATIC_ANIME_TYPES) > 0
