"""Anti-corruption layer de TioAnime: traduce el HTML/JSON crudo del sitio
a los DTOs de `application/providers/dto.py`.

Ninguna función de este módulo devuelve ni acepta el HTML/JSON crudo como
tipo de retorno público hacia fuera del paquete `tioanime/` — todo lo que
sale de acá ya es un DTO de GeekBaku. `TioAnimeProviderAdapter` es el
único consumidor.

**Filtro de contenido para adultos, en dos capas**: la primera y
principal es estructural (`client.py` nunca construye una URL fuera de
`tioanime.com` — el dominio hermano de hentai, `tiohentai.com`, no existe
en el código). Esta segunda capa es defensiva: `is_adult_genre` descarta
cualquier género que coincida con palabras clave de contenido adulto, por
si el sitio alguna vez taggea algo así dentro de su propio directorio
(hoy no lo hace — su lista de géneros no incluye "Hentai"/"Adultos"). No
depender de un solo mecanismo es intencional.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderSeasonDTO,
    ProviderSourceDTO,
    SearchResultDTO,
)

PROVIDER_ID = "tioanime"

#: Los `src` de imagen del sitio son rutas relativas (`/uploads/thumbs/1.jpg`),
#: no URLs absolutas — `ImageUrl` (dominio) exige `http(s)://...`, así que
#: `application.aggregation.normalization.normalize_image_url` las
#: descartaba silenciosamente (`ValidationError` -> `None`) antes de que
#: llegaran a ningún response. Se resuelven a absolutas acá, en el único
#: lugar que sabe cuál es el dominio real del sitio.
_IMAGE_BASE_URL = "https://tioanime.com"


def _absolute_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return f"{_IMAGE_BASE_URL}{path if path.startswith('/') else f'/{path}'}"

#: Vocabulario cerrado confirmado en el filtro de tipo de `/directorio`.
STATIC_ANIME_TYPES = ("TV", "Movie", "OVA", "Special")

_TYPE_CODE_TO_LABEL: dict[str, str] = {
    "0": "TV",
    "1": "Movie",
    "2": "OVA",
    "3": "Special",
}

_ADULT_GENRE_KEYWORDS = ("hentai", "adulto", "adult", "xxx")

_ANIME_HREF = re.compile(r"/anime/([^/?#]+)")
_EPISODE_HREF = re.compile(r"/ver/([a-z0-9-]+)-(\d+)$")


def is_adult_genre(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in _ADULT_GENRE_KEYWORDS)


def to_external_reference(slug: str) -> ExternalReferenceDTO:
    return ExternalReferenceDTO(provider_id=PROVIDER_ID, external_id=slug)


def _search_result_thumbnail(raw_id: object) -> str | None:
    """`/api/search` no devuelve imagen, pero sí `id` — y las portadas del
    sitio siguen un patrón estable `/uploads/portadas/{id}.jpg` (el mismo
    que se ve en la página de detalle vía `anime_info`). Verificado contra
    el sitio real antes de asumirlo. Si el sitio cambiara el patrón, esto
    devolvería una URL rota, no un crash — un costo aceptable frente a no
    tener imagen en absoluto en los resultados de búsqueda."""
    if raw_id is None:
        return None
    return _absolute_url(f"/uploads/portadas/{raw_id}.jpg")


def map_search_result(raw: dict[str, object]) -> SearchResultDTO:
    """Un elemento de la respuesta JSON de `/api/search`
    (`{"id","title","slug","type"}`)."""
    return SearchResultDTO(
        provider_id=PROVIDER_ID,
        external_id=str(raw.get("slug", "")),
        title=str(raw.get("title", "")),
        thumbnail_url=_search_result_thumbnail(raw.get("id")),
        anime_type=_TYPE_CODE_TO_LABEL.get(str(raw.get("type", "")), None),
        year=None,
    )


def parse_search_results(raw_items: list[dict[str, object]]) -> list[SearchResultDTO]:
    return [map_search_result(item) for item in raw_items if item.get("slug")]


def _parse_card_items(
    html: str, *, article_class: str, href_pattern: re.Pattern[str]
) -> list[SearchResultDTO]:
    soup = BeautifulSoup(html, "lxml")
    items: list[SearchResultDTO] = []
    seen_slugs: set[str] = set()
    for article in soup.select(f"article.{article_class}"):
        link = article.find("a", href=href_pattern)
        if link is None:
            continue
        href = link.get("href")
        href_str = href if isinstance(href, str) else ""
        match = href_pattern.search(href_str)
        if match is None:
            continue
        slug = match.group(1)
        if slug in seen_slugs:
            continue
        title_tag = article.select_one(".title")
        img = article.find("img")
        title = title_tag.get_text(strip=True) if title_tag else None
        if not title and img is not None:
            alt = img.get("alt")
            title = alt if isinstance(alt, str) else None
        if not title:
            continue
        thumbnail = None
        if img is not None:
            src = img.get("src")
            thumbnail = _absolute_url(src) if isinstance(src, str) else None
        seen_slugs.add(slug)
        items.append(
            SearchResultDTO(
                provider_id=PROVIDER_ID,
                external_id=slug,
                title=title,
                thumbnail_url=thumbnail,
                anime_type=None,
                year=None,
            )
        )
    return items


def parse_directory_items(html: str) -> list[SearchResultDTO]:
    """`/directorio`: grilla de `article.anime` con `<a href="/anime/{slug}">`."""
    return _parse_card_items(html, article_class="anime", href_pattern=_ANIME_HREF)


def parse_latest_episode_items(html: str) -> list[SearchResultDTO]:
    """Home, sección "Últimos Episodios": grilla de `article.episode` con
    `<a href="/ver/{slug}-{numero}">` — se deriva el anime dueño del slug
    (todo antes del último `-numero`)."""
    return _parse_card_items(html, article_class="episode", href_pattern=_EPISODE_HREF)


def parse_genre_names(html: str) -> list[str]:
    """Lista de géneros del filtro de `/directorio`: un `<select id="genero"
    name="genero[]" multiple>` con un `<option value="slug">Nombre</option>`
    por género (un dropdown "chosen", no enlaces `<a>`) — excluye
    cualquier coincidencia con palabras clave de contenido adulto (ver
    docstring del módulo)."""
    soup = BeautifulSoup(html, "lxml")
    names: list[str] = []
    seen: set[str] = set()
    for option in soup.select("select#genero option"):
        name = option.get_text(strip=True)
        if not name or name in seen or is_adult_genre(name):
            continue
        seen.add(name)
        names.append(name)
    return names


def _extract_js_array(html: str, variable_name: str) -> list[object]:
    """Extrae `var {variable_name} = [...];` embebido en un `<script>` —
    TioAnime no usa un bloque `<script type="application/json">` propio
    (a diferencia de AnimeFLV): los datos vienen como una asignación JS
    directa, así que se recorta por regex y se parsea como JSON (la
    sintaxis de un array JS simple con strings/numbers es JSON válido).
    """
    match = re.search(
        rf"var\s+{re.escape(variable_name)}\s*=\s*(\[.*?\]);", html, re.DOTALL
    )
    if match is None:
        return []
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_anime_detail(html: str, slug: str) -> ProviderAnimeDTO:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one(".title")
    title = title_tag.get_text(strip=True) if title_tag else slug

    synopsis_tag = soup.select_one(".sinopsis")
    synopsis = synopsis_tag.get_text(strip=True) if synopsis_tag else None

    raw_type_tag = soup.select_one(".meta [class*='anime-type-']")
    raw_type = raw_type_tag.get_text(strip=True) if raw_type_tag else None

    status_tag = soup.select_one(".status")
    raw_status = status_tag.get_text(strip=True) if status_tag else None

    # Deliberadamente SIN filtrar géneros adultos acá (a diferencia de
    # `parse_genre_names`, que sí filtra porque alimenta una taxonomía
    # pública): `TioAnimeProviderAdapter.get_anime_detail` necesita ver el
    # género real para decidir si rechaza el anime completo — filtrarlo
    # acá silenciosamente dejaría pasar contenido adulto sin que el
    # adapter pudiera detectarlo.
    genres = tuple(
        a.get_text(strip=True)
        for a in soup.select('.genres a[href*="?genero="]')
        if a.get_text(strip=True)
    )

    poster = soup.select_one(".anime-single img, .thumb img")
    thumbnail_url = None
    if poster is not None:
        src = poster.get("src")
        thumbnail_url = _absolute_url(src) if isinstance(src, str) else None

    return ProviderAnimeDTO(
        reference=to_external_reference(slug),
        title=title,
        synopsis=synopsis,
        raw_type=raw_type,
        raw_status=raw_status,
        country_code=None,
        genres=genres,
        studios=(),
        producers=(),
        tags=(),
        thumbnail_url=thumbnail_url,
        banner_url=None,
        trailer_url=None,
        rating_score=None,
        episode_count=None,
        external_ids=(),
    )


def parse_episode_numbers(html: str) -> list[int]:
    """`var episodes = [3,2,1];` embebido en la página de detalle —
    TioAnime no necesita una request extra por episodio para saber
    cuáles existen (a diferencia de AnimeFLV): la URL de cada uno se
    arma directo como `/ver/{slug}-{numero}`."""
    raw = _extract_js_array(html, "episodes")
    return [int(n) for n in raw if isinstance(n, (int, float, str)) and str(n).isdigit()]


def parse_episode_page(html: str, slug: str, number: int) -> ProviderEpisodeDTO:
    """Página `/ver/{slug}-{numero}`: `var videos = [["Mega", url, _, _], ...]`
    — son URLs de embed (iframe), no de descarga como en AnimeFLV. El
    sitio no distingue SUB/LAT en este array (a diferencia de la tabla de
    AnimeFLV), así que `subtitle_language_code`/`audio_language_code`
    quedan sin poblar acá; `IngestAnimeFromProvider` ya asume japonés por
    defecto cuando no hay señal explícita.
    """
    raw_videos = _extract_js_array(html, "videos")
    sources = []
    for entry in raw_videos:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        server_name, url = entry[0], entry[1]
        if not isinstance(server_name, str) or not isinstance(url, str) or not url:
            continue
        sources.append(ProviderSourceDTO(url=url, quality="unknown", label=server_name))

    return ProviderEpisodeDTO(
        reference=ExternalReferenceDTO(provider_id=PROVIDER_ID, external_id=f"{slug}:{number}"),
        number=number,
        title=None,
        thumbnail_url=None,
        air_date=None,
        sources=tuple(sources),
    )


def build_pseudo_season(
    reference: ExternalReferenceDTO, title: str, episode_count: int
) -> ProviderSeasonDTO:
    """TioAnime tampoco modela "temporadas" dentro de un mismo anime (cada
    entrega es su propio slug de catálogo, ej. `youjo-senki-ii` separado
    de `youjo-senki`) — misma aproximación pragmática que
    `animeflv.mapper.build_pseudo_season`/`jikan.mapper.map_season`."""
    return ProviderSeasonDTO(
        reference=reference, number=1, title=title, episode_count=episode_count
    )


__all__ = [
    "PROVIDER_ID",
    "STATIC_ANIME_TYPES",
    "build_pseudo_season",
    "is_adult_genre",
    "parse_anime_detail",
    "parse_directory_items",
    "parse_episode_numbers",
    "parse_episode_page",
    "parse_genre_names",
    "parse_latest_episode_items",
    "parse_search_results",
    "to_external_reference",
]
