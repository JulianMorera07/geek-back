"""Ranking Engine.

Ordena resultados agregados por, en este orden estricto (lexicográfico —
cada criterio solo desempata cuando el anterior queda igual):

1. Prioridad del provider (la más alta entre todos los que contribuyeron).
2. Calidad de la información (`quality_score`, basado en `rating_score`).
3. Completitud (`completeness_score`, fracción de campos relevantes presentes).
4. Tiempo de respuesta (el más rápido entre los providers contribuyentes gana).

`rank_*` es la única forma "oficial" de obtener `completeness_score`/
`quality_score`: `deduplication.merge_*` deja esos campos en 0.0 a propósito,
para que el cálculo de calidad viva en un único lugar.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from geekbaku.application.aggregation.dto import (
    AggregatedAnimeDTO,
    AggregatedSearchResultDTO,
    SourceReference,
)

#: Score neutral cuando no hay señal de calidad disponible (ej. el provider
#: no reporta rating): ni penaliza ni favorece frente a un resultado con
#: rating mediocre.
_NEUTRAL_QUALITY_SCORE = 0.5


def completeness_score_anime(item: AggregatedAnimeDTO) -> float:
    checks = (
        item.synopsis is not None,
        item.thumbnail_url is not None,
        item.banner_url is not None,
        item.trailer_url is not None,
        item.rating_score is not None,
        len(item.genres) > 0,
        len(item.studios) > 0,
        len(item.producers) > 0,
        len(item.tags) > 0,
        len(item.external_ids) > 0,
    )
    return sum(checks) / len(checks)


def completeness_score_search(item: AggregatedSearchResultDTO) -> float:
    checks = (
        item.thumbnail_url is not None,
        item.anime_type is not None,
        item.year is not None,
    )
    return sum(checks) / len(checks)


def quality_score_anime(item: AggregatedAnimeDTO) -> float:
    """`rating_score` está en escala 0-10 (ver `domain.catalog.Rating`); se
    normaliza a 0-1. Sin rating disponible, score neutral (ni bueno ni malo).
    """
    if item.rating_score is None:
        return _NEUTRAL_QUALITY_SCORE
    return max(0.0, min(1.0, item.rating_score / 10.0))


def quality_score_search(_item: AggregatedSearchResultDTO) -> float:
    """`SearchResultDTO` no trae rating: no hay señal de calidad posible en
    esta etapa (recién se conoce al pedir el detalle), así que todos los
    resultados de búsqueda parten del mismo score neutral.
    """
    return _NEUTRAL_QUALITY_SCORE


def _max_priority(sources: Sequence[SourceReference]) -> int:
    return max((s.priority for s in sources), default=0)


def _min_response_time_ms(sources: Sequence[SourceReference]) -> float:
    return min((s.response_time_ms for s in sources), default=0.0)


def rank_anime(items: Sequence[AggregatedAnimeDTO]) -> list[AggregatedAnimeDTO]:
    scored = [
        dataclasses.replace(
            item,
            completeness_score=completeness_score_anime(item),
            quality_score=quality_score_anime(item),
        )
        for item in items
    ]
    return sorted(
        scored,
        key=lambda item: (
            -_max_priority(item.sources),
            -item.quality_score,
            -item.completeness_score,
            _min_response_time_ms(item.sources),
        ),
    )


def rank_search_results(
    items: Sequence[AggregatedSearchResultDTO],
) -> list[AggregatedSearchResultDTO]:
    scored = [
        dataclasses.replace(
            item,
            completeness_score=completeness_score_search(item),
            quality_score=quality_score_search(item),
        )
        for item in items
    ]
    return sorted(
        scored,
        key=lambda item: (
            -_max_priority(item.sources),
            -item.quality_score,
            -item.completeness_score,
            _min_response_time_ms(item.sources),
        ),
    )
