"""Caso de uso: obtener un Genre por id."""

from __future__ import annotations

from geekbaku.application.catalog.dto import GenreDTO
from geekbaku.application.catalog.mappers import genre_to_dto, parse_genre_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import GenreNotFoundError


class GetGenre:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, genre_id: str) -> GenreDTO:
        parsed_id = parse_genre_id(genre_id)

        async with self._uow:
            genre = await self._uow.genres.get_by_id(parsed_id)

        if genre is None:
            raise GenreNotFoundError(f"No existe un género con id '{genre_id}'.")

        return genre_to_dto(genre)
