"""Deduplication Engine.

Identifica cuándo dos (o más) resultados de providers DISTINTOS son el
mismo anime, y los fusiona en un único registro agregado que:

- conserva el campo más completo disponible entre todos los duplicados
  (preferiendo el del provider de mayor prioridad cuando varios lo tienen),
- une (sin duplicar) listas como géneros/estudios/productores/external ids,
- mantiene una referencia (`SourceReference`) hacia CADA provider que
  contribuyó, nunca solo hacia el "ganador".

Estrategia de matching, en orden de confianza:
1. Comparten un `external_id` normalizado (ej. ambos reportan `mal:16498`) →
   match seguro, sin ambigüedad. Solo aplica a `NormalizedAnimeDTO` (detalle
   completo): `SearchResultDTO` no trae external ids.
2. Mismo `type`/`anime_type` + título "suficientemente similar"
   (`titles_are_similar`, tolerante a mayúsculas/espaciado/puntuación menor)
   → match heurístico, la única señal disponible para resultados de búsqueda.

El resultado de `merge_*` deja `completeness_score`/`quality_score` en 0.0:
`ranking.py` los calcula y reemplaza — este módulo solo agrupa y fusiona
campos, no juzga calidad.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Mapping, Sequence

from geekbaku.application.aggregation.dto import (
    AggregatedAnimeDTO,
    AggregatedSearchResultDTO,
    SourceReference,
)
from geekbaku.application.aggregation.normalization import (
    normalize_image_url,
    normalize_video_url,
)
from geekbaku.application.providers.dto import (
    NormalizedAnimeDTO,
    NormalizedExternalIdDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.normalizers import normalize_genre_names

_TITLE_MATCH_THRESHOLD = 0.88
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _normalize_title_for_matching(title: str) -> str:
    return _NON_ALPHANUMERIC.sub("", title.lower())


def titles_are_similar(a: str, b: str, threshold: float = _TITLE_MATCH_THRESHOLD) -> bool:
    normalized_a = _normalize_title_for_matching(a)
    normalized_b = _normalize_title_for_matching(b)
    if not normalized_a or not normalized_b:
        return False
    if normalized_a == normalized_b:
        return True
    ratio = difflib.SequenceMatcher(None, normalized_a, normalized_b).ratio()
    return ratio >= threshold


def _external_ids_overlap(
    a: Sequence[NormalizedExternalIdDTO], b: Sequence[NormalizedExternalIdDTO]
) -> bool:
    keys_a = {(e.source, e.value) for e in a}
    keys_b = {(e.source, e.value) for e in b}
    return not keys_a.isdisjoint(keys_b)


def _merge_external_ids(
    groups: Sequence[Sequence[NormalizedExternalIdDTO]],
) -> tuple[NormalizedExternalIdDTO, ...]:
    seen: dict[tuple[str, str], NormalizedExternalIdDTO] = {}
    for external_ids in groups:
        for external_id in external_ids:
            seen.setdefault((external_id.source, external_id.value), external_id)
    return tuple(seen.values())


def _group_by[T](items: Sequence[T], matches: Callable[[T, T], bool]) -> list[list[T]]:
    groups: list[list[T]] = []
    for item in items:
        group = next((g for g in groups if any(matches(item, existing) for existing in g)), None)
        if group is not None:
            group.append(item)
        else:
            groups.append([item])
    return groups


# ---------------------------------------------------------------------------
# Search results (SearchResultDTO -> AggregatedSearchResultDTO)
# ---------------------------------------------------------------------------


def _search_results_match(a: SearchResultDTO, b: SearchResultDTO) -> bool:
    if a.anime_type and b.anime_type and a.anime_type != b.anime_type:
        return False
    return titles_are_similar(a.title, b.title)


def group_search_results(results: Sequence[SearchResultDTO]) -> list[list[SearchResultDTO]]:
    return _group_by(results, _search_results_match)


def merge_search_results(
    group: Sequence[SearchResultDTO],
    provider_priority: Mapping[str, int],
    provider_response_time_ms: Mapping[str, float],
) -> AggregatedSearchResultDTO:
    primary = max(group, key=lambda r: provider_priority.get(r.provider_id, 0))

    thumbnail_url = next(
        (normalize_image_url(r.thumbnail_url) for r in group if r.thumbnail_url), None
    )
    anime_type = next((r.anime_type for r in group if r.anime_type), None)
    year = next((r.year for r in group if r.year is not None), None)

    sources = tuple(
        SourceReference(
            provider_id=r.provider_id,
            external_id=r.external_id,
            priority=provider_priority.get(r.provider_id, 0),
            response_time_ms=provider_response_time_ms.get(r.provider_id, 0.0),
        )
        for r in group
    )

    return AggregatedSearchResultDTO(
        title=primary.title,
        thumbnail_url=thumbnail_url,
        anime_type=anime_type,
        year=year,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Anime detail (NormalizedAnimeDTO -> AggregatedAnimeDTO)
# ---------------------------------------------------------------------------


def are_same_anime(a: NormalizedAnimeDTO, b: NormalizedAnimeDTO) -> bool:
    if _external_ids_overlap(a.external_ids, b.external_ids):
        return True
    return a.type == b.type and titles_are_similar(a.title, b.title)


def group_normalized_anime(
    items: Sequence[NormalizedAnimeDTO],
) -> list[list[NormalizedAnimeDTO]]:
    return _group_by(items, are_same_anime)


def merge_normalized_anime(
    group: Sequence[NormalizedAnimeDTO],
    provider_priority: Mapping[str, int],
    provider_response_time_ms: Mapping[str, float],
) -> AggregatedAnimeDTO:
    primary = max(group, key=lambda item: provider_priority.get(item.provider_id, 0))

    synopsis = next((item.synopsis for item in group if item.synopsis), None)
    thumbnail_url = next(
        (normalize_image_url(item.thumbnail_url) for item in group if item.thumbnail_url), None
    )
    banner_url = next(
        (normalize_image_url(item.banner_url) for item in group if item.banner_url), None
    )
    trailer_url = next(
        (normalize_video_url(item.trailer_url) for item in group if item.trailer_url), None
    )
    rating_scores = [item.rating_score for item in group if item.rating_score is not None]
    rating_score = sum(rating_scores) / len(rating_scores) if rating_scores else None
    country_code = next((item.country_code for item in group if item.country_code), None)

    genres = normalize_genre_names([g for item in group for g in item.genres])
    studios = normalize_genre_names([s for item in group for s in item.studios])
    producers = normalize_genre_names([p for item in group for p in item.producers])
    tags = normalize_genre_names([t for item in group for t in item.tags])
    external_ids = _merge_external_ids([item.external_ids for item in group])

    sources = tuple(
        SourceReference(
            provider_id=item.provider_id,
            external_id=item.external_id,
            priority=provider_priority.get(item.provider_id, 0),
            response_time_ms=provider_response_time_ms.get(item.provider_id, 0.0),
        )
        for item in group
    )

    return AggregatedAnimeDTO(
        title=primary.title,
        slug=primary.slug,
        synopsis=synopsis,
        type=primary.type,
        status=primary.status,
        country_code=country_code,
        thumbnail_url=thumbnail_url,
        banner_url=banner_url,
        trailer_url=trailer_url,
        rating_score=rating_score,
        genres=genres,
        studios=studios,
        producers=producers,
        tags=tags,
        external_ids=external_ids,
        sources=sources,
    )
