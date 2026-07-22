"""Caso de uso: crear un Genre."""

from __future__ import annotations

from geekbaku.application.catalog.dto import CreateGenreCommand, GenreDTO
from geekbaku.application.catalog.mappers import genre_to_dto, parse_slug
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Genre
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from geekbaku.domain.catalog.value_objects import GenreId


class CreateGenre:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: CreateGenreCommand) -> GenreDTO:
        slug = parse_slug(command.slug)

        async with self._uow:
            if await self._uow.genres.exists_by_slug(slug):
                raise DuplicateSlugError(f"Ya existe un género con el slug '{slug}'.")

            genre = Genre(id=GenreId.new(), name=command.name, slug=slug)
            await self._uow.genres.add(genre)
            await self._uow.commit()

        return genre_to_dto(genre)
