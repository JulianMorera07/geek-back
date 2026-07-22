"""Caso de uso: listar todos los Genre disponibles."""

from __future__ import annotations

from geekbaku.application.catalog.dto import GenreDTO
from geekbaku.application.catalog.mappers import genre_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork


class ListGenres:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[GenreDTO, ...]:
        async with self._uow:
            genres = await self._uow.genres.list_all()

        return tuple(genre_to_dto(genre) for genre in genres)
