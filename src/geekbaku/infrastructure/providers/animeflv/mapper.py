"""Anti-corruption layer de AnimeFLV: traduce el HTML crudo del sitio a
los DTOs de `application/providers/dto.py`, usando BeautifulSoup4 (+lxml).

Ninguna función de este módulo devuelve ni acepta el HTML/soup crudo como
tipo de retorno público hacia fuera del paquete `animeflv/` — todo lo que
sale de acá ya es un DTO de GeekBaku. `AnimeFlvProviderAdapter` es el
único consumidor.

A diferencia de Jikan (JSON documentado y estable), acá se depende de la
estructura HTML observada del sitio (clases CSS, JSON embebido en
`<script>`), que puede cambiar sin aviso — un riesgo inherente al
scraping, no un descuido. Cada selector no trivial está documentado con
la estructura concreta que asume.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Tag

from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderSeasonDTO,
    ProviderSourceDTO,
    SearchResultDTO,
)

PROVIDER_ID = "animeflv"

#: El sitio no expone una taxonomía de "tipo" (TV/Movie/OVA) navegable —
#: se usa un vocabulario cerrado estándar como fallback razonable, mismo
#: criterio que `jikan.mapper.STATIC_ANIME_TYPES`.
STATIC_ANIME_TYPES = ("TV", "Movie", "OVA", "ONA", "Special")

_ANIME_HREF = re.compile(r"/anime/([^/]+)/?")
_EPISODE_HREF = re.compile(r"/([a-z0-9-]+)-episodio-\d+/?$")
_EPISODE_TITLE_SUFFIX = re.compile(r"\s*[Ee]pisodio\s*\d+.*$")


def to_external_reference(slug: str) -> ExternalReferenceDTO:
    return ExternalReferenceDTO(provider_id=PROVIDER_ID, external_id=slug)


def _slug_from_anime_href(href: str) -> str | None:
    match = _ANIME_HREF.search(href)
    return match.group(1) if match else None


def _as_str(value: object) -> str:
    """BeautifulSoup tipa atributos como `str | AttributeValueList | None`
    (un atributo HTML puede ser multivaluado, ej. `class`) — acá siempre
    se usa como texto simple, así que se normaliza a `str`."""
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value) if value is not None else ""


def _thumbnail_from(tag: Tag) -> str | None:
    img = tag.find("img")
    if img is None:
        return None
    src = img.get("src") or img.get("data-src")
    return str(src) if src else None


def _strip_episode_suffix(title: str) -> str:
    return _EPISODE_TITLE_SUFFIX.sub("", title).strip()


def parse_listing_items(html: str) -> list[SearchResultDTO]:
    """Catálogo (`?anime_page=`) o "Animes en Emisión" (home): grilla de
    posts de WordPress, cada item con clase `ht_grid_1_4` (contiene
    `<a href="/anime/{slug}/">` + `<img>`). Deliberadamente scopeado a
    esta clase (no a "cualquier `<a href*=/anime/>` de la página"): la
    página también puede tener widgets de sidebar con enlaces a `/anime/`
    que no son parte de esta grilla.
    """
    soup = BeautifulSoup(html, "lxml")
    items: list[SearchResultDTO] = []
    seen_slugs: set[str] = set()
    for card in soup.select('[class*="ht_grid_"]'):
        link = card.find("a", href=_ANIME_HREF)
        if link is None:
            continue
        href = _as_str(link.get("href"))
        slug = _slug_from_anime_href(href)
        if slug is None or slug in seen_slugs:
            continue
        # El título vive en `.entry-title`, NO en el texto completo del
        # `<a>`: ese también incluye el badge "ESTRENO" (`.Estreno`) sin
        # separador, que quedaría pegado al título si se usa
        # `link.get_text()` directo.
        title_tag = card.select_one(".entry-title")
        img = card.find("img")
        title = (
            title_tag.get_text(strip=True)
            if title_tag is not None
            else _as_str(img.get("alt")) if img is not None else ""
        )
        if not title:
            continue
        seen_slugs.add(slug)
        items.append(
            SearchResultDTO(
                provider_id=PROVIDER_ID,
                external_id=slug,
                title=title,
                thumbnail_url=_thumbnail_from(card),
                anime_type=None,
                year=None,
            )
        )
    return items


def parse_search_results(html: str) -> list[SearchResultDTO]:
    """Resultados de `?s={query}`: grilla dedicada
    (`.search-series-grid .search-series-card`), distinta de la del
    catálogo/home — un HTML de búsqueda distinto al de catálogo, no una
    variación menor del mismo markup.
    """
    soup = BeautifulSoup(html, "lxml")
    items: list[SearchResultDTO] = []
    seen_slugs: set[str] = set()
    for card in soup.select(".search-series-card"):
        link = card.find("a", href=_ANIME_HREF)
        if link is None:
            continue
        href = _as_str(link.get("href"))
        slug = _slug_from_anime_href(href)
        if slug is None or slug in seen_slugs:
            continue
        title_tag = card.select_one(".entry-title")
        img = card.find("img")
        title = (
            title_tag.get_text(strip=True)
            if title_tag is not None
            else _as_str(img.get("alt")) if img is not None else ""
        )
        if not title:
            continue
        seen_slugs.add(slug)
        items.append(
            SearchResultDTO(
                provider_id=PROVIDER_ID,
                external_id=slug,
                title=title,
                thumbnail_url=_thumbnail_from(card),
                anime_type=None,
                year=None,
            )
        )
    return items


def parse_latest_episode_items(html: str) -> list[SearchResultDTO]:
    """Sección "Últimos episodios": cada item enlaza a un EPISODIO, no a
    un anime, pero `ProviderPort.get_latest` devuelve `SearchResultDTO`
    (animes) — se deriva el anime dueño de cada episodio a partir del
    slug de la URL (`.../{anime-slug}-episodio-{n}/`), y se descartan
    duplicados (un mismo anime puede aparecer con varios episodios
    recientes).
    """
    soup = BeautifulSoup(html, "lxml")
    items: list[SearchResultDTO] = []
    seen_slugs: set[str] = set()
    for link in soup.select('a[href*="-episodio-"]'):
        href = _as_str(link.get("href"))
        match = _EPISODE_HREF.search(href)
        if match is None:
            continue
        slug = match.group(1)
        if slug in seen_slugs:
            continue
        title = _as_str(link.get("title")) or link.get_text(strip=True)
        if not title:
            continue
        seen_slugs.add(slug)
        items.append(
            SearchResultDTO(
                provider_id=PROVIDER_ID,
                external_id=slug,
                title=_strip_episode_suffix(title),
                thumbnail_url=_thumbnail_from(link),
                anime_type=None,
                year=None,
            )
        )
    return items


def parse_genre_names(html: str) -> list[str]:
    """Agrega los géneros distintos vistos en una página de catálogo
    (clase `genre-{slug}` en cada item de grilla). El sitio no expone una
    taxonomía canónica separada (ver `docs/architecture.md`), así que
    esto es un best-effort sobre lo que aparece en la página dada, no una
    lista completa garantizada.
    """
    soup = BeautifulSoup(html, "lxml")
    genres: set[str] = set()
    for tag in soup.select('[class*="genre-"]'):
        class_value = tag.get("class")
        css_classes = class_value if isinstance(class_value, list) else []
        for css_class in css_classes:
            if css_class.startswith("genre-") and css_class != "genre-tag":
                genres.add(css_class.removeprefix("genre-").replace("-", " ").title())
    return sorted(genres)


def parse_anime_detail(html: str, slug: str) -> ProviderAnimeDTO:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("h1")
    title = title_tag.get_text(strip=True) if title_tag else slug

    # `.anime-synopsis` envuelve un `<h3>Sinopsis</h3>` (el título de la
    # sección) además del párrafo real — seleccionar el contenedor entero
    # pega ambos textos sin espacio. Se apunta al `<p>` específicamente.
    synopsis_tag = soup.select_one(".anime-synopsis p")
    synopsis = synopsis_tag.get_text(strip=True) if synopsis_tag else None

    genres = tuple(
        tag.get_text(strip=True) for tag in soup.select(".anime-genres .genre-tag")
    )

    poster = soup.select_one(".anime-poster img, .poster-image")
    thumbnail_url = None
    if poster is not None:
        thumbnail_url = poster.get("src") or poster.get("data-src")

    rating_tag = soup.select_one(".rating-score")
    rating_score: float | None = None
    if rating_tag is not None:
        try:
            rating_score = float(rating_tag.get_text(strip=True))
        except ValueError:
            rating_score = None

    return ProviderAnimeDTO(
        reference=to_external_reference(slug),
        title=title,
        synopsis=synopsis,
        raw_type=None,
        raw_status=None,
        country_code=None,
        genres=genres,
        studios=(),
        producers=(),
        tags=(),
        thumbnail_url=str(thumbnail_url) if thumbnail_url else None,
        banner_url=None,
        trailer_url=None,
        rating_score=rating_score,
        episode_count=None,
        external_ids=(),
    )


def parse_episode_refs(html: str) -> list[dict[str, object]]:
    """Extrae la lista de episodios embebida como JSON en la página de
    detalle del anime (`<script type="application/json"
    class="animeflv-episodes-data">[{"post_id":.., "permalink":..,
    "number":..}, ...]</script>`) — la lista de episodios NO está en el
    HTML como enlaces `<a>`, se renderiza client-side desde este JSON.
    """
    soup = BeautifulSoup(html, "lxml")
    script = soup.select_one("script.animeflv-episodes-data")
    if script is None or not script.string:
        return []
    try:
        raw_refs = json.loads(script.string)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_refs, list):
        return []
    return [ref for ref in raw_refs if isinstance(ref, dict)]


def parse_episode_page(
    html: str, anime_slug: str, post_id: object, number: int
) -> ProviderEpisodeDTO:
    """Página de un episodio individual: título + tabla de servidores de
    descarga/reproducción (`table.styled-table`, columnas SERVIDOR /
    TAMAÑO-FORMATO / SUB-LAT / DESCARGAR).
    """
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    sources: list[ProviderSourceDTO] = []
    for row in soup.select("table.styled-table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        server_name = cells[0].get_text(strip=True)
        format_label = cells[1].get_text(strip=True)
        language_label = cells[2].get_text(strip=True)
        link = cells[3].find("a", href=True)
        if link is None:
            continue
        sources.append(
            ProviderSourceDTO(
                url=_as_str(link["href"]),
                quality=format_label or "unknown",
                audio_language_code=None,
                subtitle_language_code="es" if "sub" in language_label.lower() else None,
                label=server_name or None,
            )
        )

    return ProviderEpisodeDTO(
        reference=ExternalReferenceDTO(
            provider_id=PROVIDER_ID, external_id=f"{anime_slug}:{post_id}"
        ),
        number=number,
        title=title,
        thumbnail_url=None,
        air_date=None,
        sources=tuple(sources),
    )


def build_pseudo_season(
    reference: ExternalReferenceDTO, title: str, episode_count: int
) -> ProviderSeasonDTO:
    """AnimeFLV no modela "temporadas" dentro de un mismo anime: cada
    temporada es una entrada de catálogo separada (ej. `grand-blue-season-3`
    es su propio slug, no una sub-página de `grand-blue`). Como
    aproximación pragmática, se devuelve una única `ProviderSeasonDTO`
    (temporada 1) — mismo criterio que `jikan.mapper.map_season`.
    """
    return ProviderSeasonDTO(
        reference=reference, number=1, title=title, episode_count=episode_count
    )


__all__ = [
    "PROVIDER_ID",
    "STATIC_ANIME_TYPES",
    "build_pseudo_season",
    "parse_anime_detail",
    "parse_episode_page",
    "parse_episode_refs",
    "parse_genre_names",
    "parse_latest_episode_items",
    "parse_listing_items",
    "to_external_reference",
]
