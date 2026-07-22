"""Caso de uso: añadir un Episode a una Season existente."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AddEpisodeCommand, EpisodeDTO
from geekbaku.application.catalog.mappers import (
    episode_to_dto,
    parse_anime_id,
    parse_episode_number,
    parse_season_id,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Episode
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import Duration, EpisodeId, Synopsis, Title


class AddEpisode:
    """Agrega un Episode a una Season de un Anime. Rechaza números de
    episodio duplicados dentro de la misma Season (`Season.add_episode`).
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: AddEpisodeCommand) -> EpisodeDTO:
        anime_id = parse_anime_id(command.anime_id)
        season_id = parse_season_id(command.season_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
            if anime is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            season = anime.get_season(season_id)

            episode = Episode(
                id=EpisodeId.new(),
                number=parse_episode_number(command.number),
                title=Title(command.title),
                synopsis=Synopsis(command.synopsis) if command.synopsis else None,
                duration=(
                    Duration(command.duration_minutes) if command.duration_minutes else None
                ),
                air_date=command.air_date,
            )
            season.add_episode(episode)

            await self._uow.animes.update(anime)
            await self._uow.commit()

        return episode_to_dto(episode)
