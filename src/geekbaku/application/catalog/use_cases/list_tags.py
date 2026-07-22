"""Caso de uso: listar todos los Tag disponibles."""

from __future__ import annotations

from geekbaku.application.catalog.dto import TagDTO
from geekbaku.application.catalog.mappers import tag_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork


class ListTags:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[TagDTO, ...]:
        async with self._uow:
            tags = await self._uow.tags.list_all()

        return tuple(tag_to_dto(tag) for tag in tags)
