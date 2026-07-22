"""Caso de uso: obtener la estructura de navegación del catálogo interno
(tipos, estados, géneros, estudios, productores, tags) para que el
frontend arme sus filtros de búsqueda/browse en una sola llamada.
"""

from __future__ import annotations

from geekbaku.application.catalog.dto import CatalogFacetsDTO
from geekbaku.application.catalog.mappers import (
    genre_to_dto,
    producer_to_dto,
    studio_to_dto,
    tag_to_dto,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.value_objects import AnimeStatus, AnimeType


class GetCatalogFacets:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> CatalogFacetsDTO:
        async with self._uow:
            genres = await self._uow.genres.list_all()
            studios = await self._uow.studios.list_all()
            producers = await self._uow.producers.list_all()
            tags = await self._uow.tags.list_all()

        return CatalogFacetsDTO(
            types=tuple(str(t) for t in AnimeType),
            statuses=tuple(str(s) for s in AnimeStatus),
            genres=tuple(genre_to_dto(g) for g in genres),
            studios=tuple(studio_to_dto(s) for s in studios),
            producers=tuple(producer_to_dto(p) for p in producers),
            tags=tuple(tag_to_dto(t) for t in tags),
        )
