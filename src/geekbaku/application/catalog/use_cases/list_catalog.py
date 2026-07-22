"""Caso de uso: listar el catálogo de Anime, paginado y filtrado."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AnimeSummaryDTO, ListCatalogQuery
from geekbaku.application.catalog.mappers import (
    anime_to_summary_dto,
    parse_anime_status,
    parse_anime_type,
    parse_genre_id,
    parse_producer_id,
    parse_studio_id,
    parse_tag_id,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.common.pagination import Page, Pagination
from geekbaku.domain.catalog.value_objects import AnimeFilter


class ListCatalog:
    """Devuelve una página de `AnimeSummaryDTO` según los filtros recibidos."""

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListCatalogQuery) -> Page[AnimeSummaryDTO]:
        filters = AnimeFilter(
            status=parse_anime_status(query.status) if query.status else None,
            type=parse_anime_type(query.type) if query.type else None,
            country_code=query.country_code,
            genre_id=parse_genre_id(query.genre_id) if query.genre_id else None,
            studio_id=parse_studio_id(query.studio_id) if query.studio_id else None,
            producer_id=parse_producer_id(query.producer_id) if query.producer_id else None,
            tag_id=parse_tag_id(query.tag_id) if query.tag_id else None,
            search_text=query.search_text,
        )
        pagination = Pagination(page=query.page, page_size=query.page_size)

        async with self._uow:
            animes, total = await self._uow.animes.list(filters, pagination)

        return Page(
            items=tuple(anime_to_summary_dto(anime) for anime in animes),
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
