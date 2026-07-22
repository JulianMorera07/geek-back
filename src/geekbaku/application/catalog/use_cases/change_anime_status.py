"""Caso de uso: cambiar el estado de emisión de un Anime."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AnimeDetailDTO, ChangeAnimeStatusCommand
from geekbaku.application.catalog.mappers import (
    anime_to_detail_dto,
    parse_anime_id,
    parse_anime_status,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


class ChangeAnimeStatus:
    """Aplica una transición de `AnimeStatus`, validada por el propio agregado
    `Anime` (`Anime.change_status`), que rechaza transiciones inválidas.
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: ChangeAnimeStatusCommand) -> AnimeDetailDTO:
        anime_id = parse_anime_id(command.anime_id)
        new_status = parse_anime_status(command.new_status)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
            if anime is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            anime.change_status(new_status)

            await self._uow.animes.update(anime)
            await self._uow.commit()

        return anime_to_detail_dto(anime)
