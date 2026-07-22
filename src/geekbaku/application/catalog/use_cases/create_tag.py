"""Caso de uso: crear un Tag."""

from __future__ import annotations

from geekbaku.application.catalog.dto import CreateTagCommand, TagDTO
from geekbaku.application.catalog.mappers import parse_slug, tag_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Tag
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from geekbaku.domain.catalog.value_objects import TagId


class CreateTag:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: CreateTagCommand) -> TagDTO:
        slug = parse_slug(command.slug)

        async with self._uow:
            if await self._uow.tags.exists_by_slug(slug):
                raise DuplicateSlugError(f"Ya existe un tag con el slug '{slug}'.")

            tag = Tag(id=TagId.new(), name=command.name, slug=slug)
            await self._uow.tags.add(tag)
            await self._uow.commit()

        return tag_to_dto(tag)
