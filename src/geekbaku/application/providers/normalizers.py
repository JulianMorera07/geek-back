"""Normalización de datos crudos de providers hacia el vocabulario de dominio.

Cada provider describe tipo/estado con su propio vocabulario libre (ej. "TV
Series", "Currently Airing", "Finished"). Este módulo traduce esas variantes
a nuestros `AnimeType`/`AnimeStatus` mediante coincidencia best-effort de
palabras clave. Es deliberadamente conservador: ante un valor desconocido,
cae a un default documentado en vez de fallar, porque un dato de un
proveedor externo con formato inesperado no debería tumbar la búsqueda o el
detalle completos.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from geekbaku.application.providers.dto import (
    NormalizedAnimeDTO,
    NormalizedEpisodeDTO,
    NormalizedExternalIdDTO,
    NormalizedRelatedDTO,
    NormalizedSeasonDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
)
from geekbaku.domain.catalog.value_objects import (
    AnimeStatus,
    AnimeType,
    ExternalIdSource,
    RelationType,
)

#: Orden relevante: se evalúa de arriba hacia abajo, la primera palabra clave
#: que aparezca en el texto crudo (en minúsculas) determina el resultado.
_TYPE_KEYWORDS: tuple[tuple[str, AnimeType], ...] = (
    ("movie", AnimeType.MOVIE),
    ("film", AnimeType.MOVIE),
    ("ova", AnimeType.OVA),
    ("ona", AnimeType.ONA),
    ("special", AnimeType.SPECIAL),
    ("music", AnimeType.MUSIC),
    ("tv", AnimeType.TV),
    ("series", AnimeType.TV),
)

_STATUS_KEYWORDS: tuple[tuple[str, AnimeStatus], ...] = (
    ("cancel", AnimeStatus.CANCELLED),
    ("hiatus", AnimeStatus.PAUSED),
    ("pause", AnimeStatus.PAUSED),
    ("complet", AnimeStatus.COMPLETED),
    ("finish", AnimeStatus.COMPLETED),
    ("end", AnimeStatus.COMPLETED),
    ("airing", AnimeStatus.ONGOING),
    ("ongoing", AnimeStatus.ONGOING),
    ("releasing", AnimeStatus.ONGOING),
    ("announc", AnimeStatus.ANNOUNCED),
    ("upcoming", AnimeStatus.ANNOUNCED),
    ("not yet", AnimeStatus.ANNOUNCED),
)

_RELATION_KEYWORDS: tuple[tuple[str, RelationType], ...] = (
    ("sequel", RelationType.SEQUEL),
    ("prequel", RelationType.PREQUEL),
    ("side story", RelationType.SIDE_STORY),
    ("parent story", RelationType.PARENT_STORY),
    ("spin", RelationType.SPIN_OFF),
    ("alternative", RelationType.ALTERNATIVE_VERSION),
    ("adaptation", RelationType.ADAPTATION),
    ("summary", RelationType.SUMMARY),
)

_EXTERNAL_ID_SOURCE_KEYWORDS: tuple[tuple[str, ExternalIdSource], ...] = (
    ("myanimelist", ExternalIdSource.MAL),
    ("mal", ExternalIdSource.MAL),
    ("anilist", ExternalIdSource.ANILIST),
    ("tmdb", ExternalIdSource.TMDB),
    ("themoviedb", ExternalIdSource.TMDB),
    ("imdb", ExternalIdSource.IMDB),
    ("tvdb", ExternalIdSource.TVDB),
    ("kitsu", ExternalIdSource.KITSU),
)

#: Defaults usados cuando el provider no da tipo/estado/relación/fuente de
#: external id, o el valor no coincide con ninguna palabra clave conocida.
DEFAULT_ANIME_TYPE = AnimeType.TV
DEFAULT_ANIME_STATUS = AnimeStatus.ANNOUNCED
DEFAULT_RELATION_TYPE = RelationType.OTHER
DEFAULT_EXTERNAL_ID_SOURCE = ExternalIdSource.OTHER

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_type(raw_type: str | None) -> AnimeType:
    if raw_type is None:
        return DEFAULT_ANIME_TYPE
    lowered = raw_type.lower()
    for keyword, anime_type in _TYPE_KEYWORDS:
        if keyword in lowered:
            return anime_type
    return DEFAULT_ANIME_TYPE


def normalize_status(raw_status: str | None) -> AnimeStatus:
    if raw_status is None:
        return DEFAULT_ANIME_STATUS
    lowered = raw_status.lower()
    for keyword, status in _STATUS_KEYWORDS:
        if keyword in lowered:
            return status
    return DEFAULT_ANIME_STATUS


def normalize_relation_type(raw_relation_type: str | None) -> RelationType:
    if raw_relation_type is None:
        return DEFAULT_RELATION_TYPE
    lowered = raw_relation_type.lower()
    for keyword, relation_type in _RELATION_KEYWORDS:
        if keyword in lowered:
            return relation_type
    return DEFAULT_RELATION_TYPE


def normalize_genre_names(raw_genres: Sequence[str]) -> tuple[str, ...]:
    """Limpia una lista de nombres libres (espacios, duplicados), preservando
    el orden de aparición. Pese al nombre (histórico, desde que solo se usaba
    para géneros), es genérica: también se reusa para `studios`/`producers`.
    No resuelve nada contra nuestros repositorios propios (`GenreRepository`,
    `StudioRepository`, `ProducerRepository` son catálogos con slug e id):
    esa coincidencia/creación es responsabilidad de una futura capa de
    ingesta, fuera de alcance de este sprint.
    """
    seen: dict[str, None] = {}
    for raw in raw_genres:
        cleaned = _WHITESPACE.sub(" ", raw.strip())
        if cleaned:
            seen.setdefault(cleaned, None)
    return tuple(seen.keys())


def normalize_external_id_source(raw_source: str) -> ExternalIdSource:
    lowered = raw_source.lower()
    for keyword, source in _EXTERNAL_ID_SOURCE_KEYWORDS:
        if keyword in lowered:
            return source
    return DEFAULT_EXTERNAL_ID_SOURCE


def normalize_external_ids(
    raw_external_ids: Sequence[tuple[str, str]],
) -> tuple[NormalizedExternalIdDTO, ...]:
    seen: dict[tuple[str, str], None] = {}
    for raw_source, value in raw_external_ids:
        cleaned_value = value.strip()
        if not cleaned_value:
            continue
        key = (str(normalize_external_id_source(raw_source)), cleaned_value)
        seen.setdefault(key, None)
    return tuple(NormalizedExternalIdDTO(source=source, value=value) for source, value in seen)


def slugify(title: str) -> str:
    """Genera un slug kebab-case a partir de un título arbitrario.

    Usado cuando el provider no entrega un slug propio. No garantiza
    unicidad global: eso es responsabilidad de quien persista el resultado
    (fuera de alcance de este sprint).
    """
    lowered = title.strip().lower()
    slug = _SLUG_INVALID_CHARS.sub("-", lowered).strip("-")
    return slug or "untitled"


def to_normalized_anime(provider_anime: ProviderAnimeDTO) -> NormalizedAnimeDTO:
    """Convierte el detalle crudo de un provider a nuestro vocabulario."""
    return NormalizedAnimeDTO(
        provider_id=provider_anime.reference.provider_id,
        external_id=provider_anime.reference.external_id,
        title=provider_anime.title,
        slug=slugify(provider_anime.title),
        synopsis=provider_anime.synopsis,
        type=str(normalize_type(provider_anime.raw_type)),
        status=str(normalize_status(provider_anime.raw_status)),
        country_code=provider_anime.country_code,
        thumbnail_url=provider_anime.thumbnail_url,
        banner_url=provider_anime.banner_url,
        trailer_url=provider_anime.trailer_url,
        rating_score=provider_anime.rating_score,
        genres=normalize_genre_names(provider_anime.genres),
        studios=normalize_genre_names(provider_anime.studios),
        producers=normalize_genre_names(provider_anime.producers),
        tags=provider_anime.tags,
        external_ids=normalize_external_ids(provider_anime.external_ids),
    )


def to_normalized_episode(provider_episode: ProviderEpisodeDTO) -> NormalizedEpisodeDTO:
    """Convierte un episodio crudo de un provider a nuestro vocabulario."""
    return NormalizedEpisodeDTO(
        provider_id=provider_episode.reference.provider_id,
        external_id=provider_episode.reference.external_id,
        number=provider_episode.number,
        title=provider_episode.title,
        thumbnail_url=provider_episode.thumbnail_url,
        air_date=provider_episode.air_date,
        sources=provider_episode.sources,
    )


def to_normalized_season(provider_season: ProviderSeasonDTO) -> NormalizedSeasonDTO:
    """Convierte una temporada cruda de un provider a nuestro vocabulario."""
    return NormalizedSeasonDTO(
        provider_id=provider_season.reference.provider_id,
        external_id=provider_season.reference.external_id,
        number=provider_season.number,
        title=provider_season.title,
        episode_count=provider_season.episode_count,
    )


def to_normalized_related(provider_related: ProviderRelatedDTO) -> NormalizedRelatedDTO:
    """Convierte un anime relacionado crudo de un provider a nuestro vocabulario."""
    return NormalizedRelatedDTO(
        provider_id=provider_related.reference.provider_id,
        external_id=provider_related.reference.external_id,
        title=provider_related.title,
        relation_type=str(normalize_relation_type(provider_related.raw_relation_type)),
    )
