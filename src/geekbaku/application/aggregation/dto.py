"""DTOs del Aggregation Engine.

Un `AggregatedSearchResultDTO`/`AggregatedAnimeDTO` puede representar
información fusionada de VARIOS providers (`sources`) cuando el
Deduplication Engine determinó que dos o más resultados de providers
distintos son el mismo anime. Nunca se construyen a mano fuera de
`deduplication.py`/`ranking.py`: `merge_*` los crea con scores en 0.0,
`rank_*` los reemplaza con los scores calculados y el orden final.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from geekbaku.application.providers.dto import NormalizedExternalIdDTO


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Un provider concreto que contribuyó a un resultado agregado."""

    provider_id: str
    external_id: str
    priority: int
    response_time_ms: float


@dataclass(frozen=True, slots=True)
class AggregatedSearchResultDTO:
    """Resultado de búsqueda ya deduplicado/fusionado/rankeado."""

    title: str
    thumbnail_url: str | None
    anime_type: str | None
    year: int | None
    sources: tuple[SourceReference, ...] = field(default_factory=tuple)
    completeness_score: float = 0.0
    quality_score: float = 0.0


@dataclass(frozen=True, slots=True)
class AggregatedAnimeDTO:
    """Detalle de un Anime, potencialmente fusionado desde varios providers."""

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
    genres: tuple[str, ...] = field(default_factory=tuple)
    studios: tuple[str, ...] = field(default_factory=tuple)
    producers: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    external_ids: tuple[NormalizedExternalIdDTO, ...] = field(default_factory=tuple)
    sources: tuple[SourceReference, ...] = field(default_factory=tuple)
    completeness_score: float = 0.0
    quality_score: float = 0.0
