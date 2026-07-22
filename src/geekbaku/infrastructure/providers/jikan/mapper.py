"""Anti-corruption layer de Jikan: traduce el JSON crudo de la API a los
DTOs de `application/providers/dto.py`.

Ninguna función de este módulo devuelve ni acepta el JSON crudo de Jikan
como tipo de retorno público hacia fuera del paquete `jikan/` — todo lo que
sale de acá ya es un DTO de GeekBaku. `JikanProviderAdapter` es el único
consumidor de este módulo.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)

#: Identificador de este provider dentro del `ProviderRegistry` de GeekBaku.
PROVIDER_ID = "jikan"

#: Jikan/MAL no expone un endpoint de "tipos" separado; es un vocabulario
#: cerrado y estable de su propio dominio, documentado en su API.
STATIC_ANIME_TYPES = ("TV", "Movie", "OVA", "ONA", "Special", "Music")

JsonDict = dict[str, Any]


def _extract_image_url(raw: JsonDict) -> str | None:
    jpg = raw.get("images", {}).get("jpg", {})
    url = jpg.get("large_image_url") or jpg.get("image_url")
    return str(url) if url else None


def _extract_trailer_url(raw: JsonDict) -> str | None:
    trailer = raw.get("trailer") or {}
    url = trailer.get("url")
    return url if isinstance(url, str) and url else None


def _parse_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value).date()
    except ValueError:
        return None


def to_external_reference(mal_id: object) -> ExternalReferenceDTO:
    return ExternalReferenceDTO(provider_id=PROVIDER_ID, external_id=str(mal_id))


def map_search_result(raw: JsonDict) -> SearchResultDTO:
    """Un elemento de `data` de `/anime`, `/seasons/now` o `/top/anime`."""
    return SearchResultDTO(
        provider_id=PROVIDER_ID,
        external_id=str(raw["mal_id"]),
        title=raw.get("title") or "",
        thumbnail_url=_extract_image_url(raw),
        anime_type=raw.get("type"),
        year=raw.get("year"),
    )


def map_anime_detail(raw: JsonDict) -> ProviderAnimeDTO:
    """`data` de `/anime/{id}/full`.

    Jikan no expone país de origen ni "banner" distinto del cover: se
    asume `country_code="JP"` (MyAnimeList es un catálogo de anime
    japonés) y no se rellena `banner_url`. `tags` combina "themes" y
    "demographics" de MAL, que no tienen un equivalente 1:1 con `genres`
    en nuestro dominio pero se acercan más al concepto de `Tag` (libre,
    granular) que al de `Genre`. `producers` viene del array `producers` de
    Jikan (distinto de `studios`: son las compañías que financian/licencian,
    no quien anima). `external_ids` se autoreferencia con el propio
    `mal_id` (fuente `"mal"`) — es lo único que Jikan expone sin llamar a un
    endpoint adicional, pero alcanza para que el Aggregation Engine (Sprint
    6) pueda cruzarlo con lo que reporten otros proveedores.
    """
    genres = tuple(g["name"] for g in raw.get("genres", []) if "name" in g)
    themes = tuple(t["name"] for t in raw.get("themes", []) if "name" in t)
    demographics = tuple(d["name"] for d in raw.get("demographics", []) if "name" in d)
    studios = tuple(s["name"] for s in raw.get("studios", []) if "name" in s)
    producers = tuple(p["name"] for p in raw.get("producers", []) if "name" in p)

    return ProviderAnimeDTO(
        reference=to_external_reference(raw["mal_id"]),
        title=raw.get("title") or "",
        synopsis=raw.get("synopsis"),
        raw_type=raw.get("type"),
        raw_status=raw.get("status"),
        country_code="JP",
        genres=genres,
        studios=studios,
        producers=producers,
        external_ids=(("mal", str(raw["mal_id"])),),
        tags=themes + demographics,
        thumbnail_url=_extract_image_url(raw),
        banner_url=None,
        trailer_url=_extract_trailer_url(raw),
        rating_score=raw.get("score"),
        episode_count=raw.get("episodes"),
    )


def map_episode(raw: JsonDict, anime_mal_id: str) -> ProviderEpisodeDTO:
    """Un elemento de `data` de `/anime/{id}/episodes`.

    `external_id` combina el id del anime y el del episodio
    (`"{anime_id}:{episode_id}"`): el `mal_id` de un episodio por sí solo
    no es una clave global en Jikan, solo es único dentro de su anime.
    """
    episode_mal_id = raw["mal_id"]
    return ProviderEpisodeDTO(
        reference=ExternalReferenceDTO(
            provider_id=PROVIDER_ID, external_id=f"{anime_mal_id}:{episode_mal_id}"
        ),
        number=int(episode_mal_id),
        title=raw.get("title"),
        thumbnail_url=None,
        air_date=_parse_date(raw.get("aired")),
    )


def map_season(anime_detail: JsonDict, reference: ExternalReferenceDTO) -> ProviderSeasonDTO:
    """Jikan/MAL no modela "temporadas" dentro de un mismo anime: cada
    cour/parte suele ser una entrada separada, vinculada por `relations`
    (ver `map_relation_group`). Como aproximación pragmática, se devuelve
    una única `ProviderSeasonDTO` (temporada 1) con el conteo total de
    episodios del anime.
    """
    return ProviderSeasonDTO(
        reference=reference,
        number=1,
        title=anime_detail.get("title"),
        episode_count=anime_detail.get("episodes"),
    )


def map_relation_group(raw_group: JsonDict) -> list[ProviderRelatedDTO]:
    """Un elemento de `data` de `/anime/{id}/relations`
    (`{"relation": "Sequel", "entry": [...]}`). Se descartan entries que no
    sean de tipo "anime" (Jikan también relaciona con manga/novelas).
    """
    relation_type = raw_group.get("relation")
    related = []
    for entry in raw_group.get("entry", []):
        if entry.get("type") != "anime":
            continue
        related.append(
            ProviderRelatedDTO(
                reference=to_external_reference(entry["mal_id"]),
                title=entry.get("name") or "",
                raw_relation_type=relation_type,
            )
        )
    return related


def map_genre_names(raw: JsonDict) -> list[str]:
    """`data` de `/genres/anime`."""
    return [g["name"] for g in raw.get("data", []) if "name" in g]
