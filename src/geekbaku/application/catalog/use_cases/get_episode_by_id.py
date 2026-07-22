"""Caso de uso: obtener un Episode por id, sin cargar el Anime completo.

Usa `EpisodeRepository` (no `AnimeRepository`): por eso el resultado no
incluye a qué Anime/Season pertenece (`EpisodeRepository` fue diseñado en
el Sprint 2 justamente para resolver esto sin el costo de cargar el
agregado completo).
"""

from __future__ import annotations

from geekbaku.application.catalog.dto import EpisodeDTO
from geekbaku.application.catalog.mappers import episode_to_dto, parse_episode_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import EpisodeNotFoundError


class GetEpisodeById:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, episode_id: str) -> EpisodeDTO:
        parsed_id = parse_episode_id(episode_id)

        async with self._uow:
            episode = await self._uow.episodes.get_by_id(parsed_id)

        if episode is None:
            raise EpisodeNotFoundError(f"No existe un episodio con id '{episode_id}'.")

        return episode_to_dto(episode)
