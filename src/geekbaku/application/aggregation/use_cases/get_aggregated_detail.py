"""Caso de uso: detalle de un Anime fusionado desde varios providers."""

from __future__ import annotations

from geekbaku.application.aggregation.dto import AggregatedAnimeDTO
from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.providers.dto import ExternalReferenceDTO


class GetAggregatedAnimeDetail:
    """Recibe las referencias (una por provider) que ya se sabe que
    corresponden al mismo anime — ej. obtenidas de un resultado de
    `SearchAggregatedAnime` (`AggregatedSearchResultDTO.sources`) — y
    devuelve el detalle fusionado.
    """

    def __init__(self, engine: AggregationEngine) -> None:
        self._engine = engine

    async def execute(
        self, references: tuple[ExternalReferenceDTO, ...]
    ) -> AggregatedAnimeDTO | None:
        return await self._engine.aggregate_detail(references)
