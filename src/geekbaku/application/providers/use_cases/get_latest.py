"""Caso de uso: obtener los últimos Anime agregados/actualizados."""

from __future__ import annotations

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.dto import SearchResultDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_provider_id


class GetLatest:
    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(
        self,
        page: int = 1,
        page_size: int = 20,
        provider_ids: tuple[str, ...] | None = None,
    ) -> list[SearchResultDTO]:
        pagination = Pagination(page=page, page_size=page_size)
        parsed_provider_ids = (
            tuple(parse_provider_id(pid) for pid in provider_ids)
            if provider_ids is not None
            else None
        )
        return await self._manager.get_latest(pagination, parsed_provider_ids)
