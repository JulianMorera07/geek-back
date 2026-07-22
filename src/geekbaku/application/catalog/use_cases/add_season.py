"""Caso de uso: añadir una Season a un Anime existente."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AddSeasonCommand, SeasonDTO
from geekbaku.application.catalog.mappers import (
    parse_anime_id,
    parse_season_number,
    season_to_dto,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Season
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import SeasonId


class AddSeason:
    """Agrega una Season a un Anime. Rechaza números de temporada duplicados
    (invariante forzada por `Anime.add_season`).
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: AddSeasonCommand) -> SeasonDTO:
        anime_id = parse_anime_id(command.anime_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
            if anime is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            season = Season(
                id=SeasonId.new(),
                number=parse_season_number(command.number),
                title=command.title,
            )
            anime.add_season(season)

            await self._uow.animes.update(anime)
            await self._uow.commit()

        return season_to_dto(season)
