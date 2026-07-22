"""Caso de uso: listar todos los Studio disponibles."""

from __future__ import annotations

from geekbaku.application.catalog.dto import StudioDTO
from geekbaku.application.catalog.mappers import studio_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork


class ListStudios:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[StudioDTO, ...]:
        async with self._uow:
            studios = await self._uow.studios.list_all()

        return tuple(studio_to_dto(studio) for studio in studios)
