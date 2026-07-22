"""DTOs del módulo de providers.

Representan datos que cruzan el límite hacia/desde un provider externo. A
diferencia de `application/catalog/dto.py` (que sirve a un store propio y
confiable), estos DTOs son el punto donde entra información NO confiable
todavía: un `ProviderPort` concreto los produce a partir de lo que sea que
el sitio externo devuelva, y `application/providers/normalizers.py` los
traduce a una forma consistente con nuestras reglas de dominio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class ExternalReferenceDTO:
    provider_id: str
    external_id: str


@dataclass(frozen=True, slots=True)
class ProviderSourceDTO:
    url: str
    quality: str
    audio_language_code: str | None = None
    subtitle_language_code: str | None = None
    label: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderEpisodeDTO:
    """Forma cruda de un episodio, tal como la entrega un provider."""

    reference: ExternalReferenceDTO
    number: int
    title: str | None = None
    thumbnail_url: str | None = None
    air_date: date | None = None
    sources: tuple[ProviderSourceDTO, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProviderAnimeDTO:
    """Forma cruda del detalle de un Anime, tal como la entrega un provider.

    Los campos de texto libre (`raw_type`, `raw_status`) reflejan el
    vocabulario propio del provider (ej. "Currently Airing"), sin normalizar
    todavía: `normalizers.to_normalized_anime` los traduce a
    `AnimeType`/`AnimeStatus`.
    """

    reference: ExternalReferenceDTO
    title: str
    synopsis: str | None = None
    raw_type: str | None = None
    raw_status: str | None = None
    country_code: str | None = None
    genres: tuple[str, ...] = field(default_factory=tuple)
    studios: tuple[str, ...] = field(default_factory=tuple)
    producers: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    thumbnail_url: str | None = None
    banner_url: str | None = None
    trailer_url: str | None = None
    rating_score: float | None = None
    episode_count: int | None = None
    #: Referencias cruzadas que el propio provider conoce hacia catálogos de
    #: metadata externos, como pares `(source, value)` sin normalizar todavía
    #: (ej. `[("mal", "16498"), ("anilist", "5114")]`). Útiles para que el
    #: Aggregation Engine (Sprint 6) pueda deduplicar por id exacto en vez de
    #: solo por similitud de título.
    external_ids: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProviderSeasonDTO:
    """Forma cruda de una temporada, tal como la entrega un provider."""

    reference: ExternalReferenceDTO
    number: int
    title: str | None = None
    episode_count: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderRelatedDTO:
    """Anime relacionado, tal como lo entrega un provider.

    `raw_relation_type` es el vocabulario propio del provider (ej. "Sequel",
    "Side Story"); `normalizers.to_normalized_related` lo traduce a
    `RelationType`.
    """

    reference: ExternalReferenceDTO
    title: str
    raw_relation_type: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResultDTO:
    provider_id: str
    external_id: str
    title: str
    thumbnail_url: str | None = None
    anime_type: str | None = None
    year: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderCatalogDTO:
    """Facetas de navegación (géneros/tipos) que expone un provider."""

    provider_id: str
    genres: tuple[str, ...]
    types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizedEpisodeDTO:
    """Episodio ya normalizado a nuestro vocabulario de dominio."""

    provider_id: str
    external_id: str
    number: int
    title: str | None
    thumbnail_url: str | None
    air_date: date | None
    sources: tuple[ProviderSourceDTO, ...]


@dataclass(frozen=True, slots=True)
class NormalizedSeasonDTO:
    """Temporada ya normalizada a nuestro vocabulario de dominio."""

    provider_id: str
    external_id: str
    number: int
    title: str | None
    episode_count: int | None


@dataclass(frozen=True, slots=True)
class NormalizedRelatedDTO:
    """Relación con otro Anime ya normalizada a nuestro vocabulario de dominio."""

    provider_id: str
    external_id: str
    title: str
    relation_type: str


@dataclass(frozen=True, slots=True)
class NormalizedExternalIdDTO:
    """Referencia cruzada normalizada (`source` ya mapeado a un
    `ExternalIdSource` de dominio, como string)."""

    source: str
    value: str


@dataclass(frozen=True, slots=True)
class NormalizedAnimeDTO:
    """Anime ya normalizado a nuestro vocabulario de dominio (`AnimeType`,
    `AnimeStatus`, slug generado si el provider no trae uno), listo para ser
    mostrado o, en un sprint futuro, usado como base de un `CreateAnimeCommand`
    de ingesta. Este sprint no persiste el resultado (no hay scraping/ingesta
    todavía), solo lo produce.
    """

    provider_id: str
    external_id: str
    title: str
    slug: str
    synopsis: str | None
    type: str
    status: str
    country_code: str | None
    thumbnail_url: str | None
    banner_url: str | None
    trailer_url: str | None
    rating_score: float | None
    genres: tuple[str, ...]
    studios: tuple[str, ...]
    producers: tuple[str, ...]
    tags: tuple[str, ...]
    external_ids: tuple[NormalizedExternalIdDTO, ...]


@dataclass(frozen=True, slots=True)
class ProviderInfoDTO:
    """Estado de un provider registrado, para la API pública (`GET /api/v1/providers`).

    Combina configuración administrativa (`StreamingProvider`, Sprint 3/4) con
    observabilidad en vivo (`ProviderHealth`/`ProviderStats`, Sprint 4/5) —
    nunca expone detalles internos del adapter (URLs base, credenciales, etc.).
    """

    provider_id: str
    display_name: str
    is_enabled: bool
    priority: int
    health_status: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_response_time_ms: float
