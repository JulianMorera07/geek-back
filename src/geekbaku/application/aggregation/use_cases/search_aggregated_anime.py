"""Caso de uso: búsqueda distribuida (Search Engine).

El usuario busca; el sistema consulta múltiples providers en paralelo vía
`ProviderManager` (Provider Framework); el Aggregation Engine deduplica,
fusiona y ordena todo en una única lista.
"""

from __future__ import annotations

from geekbaku.application.aggregation.dto import AggregatedSearchResultDTO
from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.mappers import parse_provider_id


class SearchAggregatedAnime:
    def __init__(self, engine: AggregationEngine) -> None:
        self._engine = engine

    async def execute(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        provider_ids: tuple[str, ...] | None = None,
    ) -> list[AggregatedSearchResultDTO]:
        pagination = Pagination(page=page, page_size=page_size)
        parsed_provider_ids = (
            tuple(parse_provider_id(pid) for pid in provider_ids)
            if provider_ids is not None
            else None
        )
        return await self._engine.search(query, pagination, parsed_provider_ids)
