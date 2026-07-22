"""Caso de uso: listar todos los episodios de un Anime, aplanados a través
de sus Seasons (ordenados por número de temporada y luego de episodio).
"""

from __future__ import annotations

from geekbaku.application.catalog.dto import EpisodeDTO
from geekbaku.application.catalog.mappers import episode_to_dto, parse_anime_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


class GetAnimeEpisodes:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, anime_id: str) -> tuple[EpisodeDTO, ...]:
        parsed_id = parse_anime_id(anime_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(parsed_id)

        if anime is None:
            raise AnimeNotFoundError(f"No existe un anime con id '{anime_id}'.")

        ordered_seasons = sorted(anime.seasons, key=lambda season: season.number.value)
        episodes = [
            episode
            for season in ordered_seasons
            for episode in sorted(season.episodes, key=lambda episode: episode.number.value)
        ]
        return tuple(episode_to_dto(episode) for episode in episodes)
