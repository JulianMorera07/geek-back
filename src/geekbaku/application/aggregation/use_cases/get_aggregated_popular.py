"""Caso de uso: obtener los Anime más populares, deduplicados y ordenados
entre todos los providers registrados.
"""

from __future__ import annotations

from geekbaku.application.aggregation.dto import AggregatedSearchResultDTO
from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.mappers import parse_provider_id


class GetAggregatedPopular:
    def __init__(self, engine: AggregationEngine) -> None:
        self._engine = engine

    async def execute(
        self,
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
        return await self._engine.get_popular(pagination, parsed_provider_ids)
