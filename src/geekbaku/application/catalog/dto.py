"""DTOs del módulo de catálogo.

Son `dataclasses` puros (no Pydantic): los schemas Pydantic viven en
`infrastructure/http/schemas` y se mapean a/desde estos DTOs en los routers.
Mantener esta separación permite que `application/` no dependa de FastAPI.

Se dividen en:
- *Command* / *Query*: entrada de un caso de uso.
- *DTO*: salida de un caso de uso (read model), siempre con tipos primitivos
  (str/int/bool/date) para no filtrar Value Objects de dominio hacia afuera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Read models (salida)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MediaDTO:
    kind: str
    url: str


@dataclass(frozen=True, slots=True)
class ExternalIdDTO:
    source: str
    value: str


@dataclass(frozen=True, slots=True)
class RelationDTO:
    related_anime_id: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class StreamingSourceDTO:
    id: str
    provider_name: str
    external_ref: str
    quality: str
    audio_language: str
    subtitle_language: str | None
    url: str | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class EpisodeDTO:
    id: str
    number: int
    title: str
    synopsis: str | None
    duration_minutes: int | None
    air_date: date | None
    media: tuple[MediaDTO, ...] = field(default_factory=tuple)
    external_ids: tuple[ExternalIdDTO, ...] = field(default_factory=tuple)
    streaming_sources: tuple[StreamingSourceDTO, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SeasonDTO:
    id: str
    number: int
    title: str | None
    episodes: tuple[EpisodeDTO, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RatingDTO:
    score: float
    votes: int | None
    source: str


@dataclass(frozen=True, slots=True)
class AnimeSummaryDTO:
    """Vista ligera para listados de catálogo."""

    id: str
    title: str
    slug: str
    type: str
    status: str
    country_code: str | None
    thumbnail_url: str | None = None
    rating: RatingDTO | None = None


@dataclass(frozen=True, slots=True)
class AnimeDetailDTO:
    """Vista completa de un Anime, incluyendo Seasons/Episodes."""

    id: str
    title: str
    slug: str
    type: str
    status: str
    synopsis: str | None
    country_code: str | None
    genre_ids: tuple[str, ...]
    studio_ids: tuple[str, ...]
    producer_ids: tuple[str, ...]
    tag_ids: tuple[str, ...]
    media: tuple[MediaDTO, ...]
    thumbnail_url: str | None
    banner_url: str | None
    trailer_url: str | None
    rating: RatingDTO | None
    external_ids: tuple[ExternalIdDTO, ...]
    relations: tuple[RelationDTO, ...]
    seasons: tuple[SeasonDTO, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GenreDTO:
    id: str
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class StudioDTO:
    id: str
    name: str
    slug: str
    country_code: str | None


@dataclass(frozen=True, slots=True)
class ProducerDTO:
    id: str
    name: str
    slug: str
    country_code: str | None


@dataclass(frozen=True, slots=True)
class TagDTO:
    id: str
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class CatalogFacetsDTO:
    """Estructura de navegación del catálogo interno: todo lo que un
    frontend necesita para construir filtros de búsqueda/browse (tipos y
    estados son enumeraciones cerradas del dominio; géneros/estudios/
    productores/tags son los catálogos abiertos ya creados).
    """

    types: tuple[str, ...]
    statuses: tuple[str, ...]
    genres: tuple[GenreDTO, ...]
    studios: tuple[StudioDTO, ...]
    producers: tuple[ProducerDTO, ...]
    tags: tuple[TagDTO, ...]


# ---------------------------------------------------------------------------
# Commands / Queries (entrada)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateAnimeCommand:
    title: str
    slug: str
    type: str
    status: str
    synopsis: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    genre_ids: tuple[str, ...] = field(default_factory=tuple)
    studio_ids: tuple[str, ...] = field(default_factory=tuple)
    producer_ids: tuple[str, ...] = field(default_factory=tuple)
    tag_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ChangeAnimeStatusCommand:
    anime_id: str
    new_status: str


@dataclass(frozen=True, slots=True)
class AddSeasonCommand:
    anime_id: str
    number: int
    title: str | None = None


@dataclass(frozen=True, slots=True)
class AddEpisodeCommand:
    anime_id: str
    season_id: str
    number: int
    title: str
    synopsis: str | None = None
    duration_minutes: int | None = None
    air_date: date | None = None


@dataclass(frozen=True, slots=True)
class AddStreamingSourceCommand:
    anime_id: str
    episode_id: str
    provider_name: str
    external_ref: str
    quality: str
    audio_language_code: str
    audio_language_name: str
    subtitle_language_code: str | None = None
    subtitle_language_name: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class AddAnimeExternalIdCommand:
    anime_id: str
    source: str
    value: str


@dataclass(frozen=True, slots=True)
class AddEpisodeExternalIdCommand:
    anime_id: str
    episode_id: str
    source: str
    value: str


@dataclass(frozen=True, slots=True)
class AddRelationCommand:
    anime_id: str
    related_anime_id: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class ListCatalogQuery:
    status: str | None = None
    type: str | None = None
    country_code: str | None = None
    genre_id: str | None = None
    studio_id: str | None = None
    producer_id: str | None = None
    tag_id: str | None = None
    search_text: str | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class CreateGenreCommand:
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class CreateStudioCommand:
    name: str
    slug: str
    country_code: str | None = None
    country_name: str | None = None


@dataclass(frozen=True, slots=True)
class CreateTagCommand:
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class CreateProducerCommand:
    name: str
    slug: str
    country_code: str | None = None
    country_name: str | None = None
