"""Caso de uso: crear un Studio."""

from __future__ import annotations

from geekbaku.application.catalog.dto import CreateStudioCommand, StudioDTO
from geekbaku.application.catalog.mappers import parse_slug, studio_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Studio
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from geekbaku.domain.catalog.value_objects import Country, StudioId


class CreateStudio:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: CreateStudioCommand) -> StudioDTO:
        slug = parse_slug(command.slug)

        async with self._uow:
            if await self._uow.studios.exists_by_slug(slug):
                raise DuplicateSlugError(f"Ya existe un estudio con el slug '{slug}'.")

            country = (
                Country(code=command.country_code, name=command.country_name)
                if command.country_code and command.country_name
                else None
            )

            studio = Studio(id=StudioId.new(), name=command.name, slug=slug, country=country)
            await self._uow.studios.add(studio)
            await self._uow.commit()

        return studio_to_dto(studio)
