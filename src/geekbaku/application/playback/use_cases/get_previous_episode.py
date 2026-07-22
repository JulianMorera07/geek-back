"""Caso de uso: obtener la referencia al episodio anterior.

Si el episodio actual es el primero de la temporada, retrocede al último
episodio de la temporada anterior. Devuelve `None` si no hay anterior
(inicio de la serie) — mismo criterio que `GetNextEpisode`.
"""

from __future__ import annotations

from geekbaku.application.catalog.mappers import parse_anime_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.playback.dto import AdjacentEpisodeQuery, EpisodeReferenceDTO
from geekbaku.domain.catalog.entities import Anime, Season
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


def _find_season(anime: Anime, season_number: int) -> Season | None:
    return next((s for s in anime.seasons if s.number.value == season_number), None)


class GetPreviousEpisode:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: AdjacentEpisodeQuery) -> EpisodeReferenceDTO | None:
        anime_id = parse_anime_id(query.anime_id)
        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
        if anime is None:
            raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

        if query.episode_number > 1:
            current_season = _find_season(anime, query.season_number)
            if current_season is not None:
                previous_in_season = next(
                    (
                        e
                        for e in current_season.episodes
                        if e.number.value == query.episode_number - 1
                    ),
                    None,
                )
                if previous_in_season is not None:
                    return EpisodeReferenceDTO(
                        anime_id=query.anime_id,
                        episode_id=str(previous_in_season.id),
                        season_number=current_season.number.value,
                        episode_number=previous_in_season.number.value,
                    )
            return None

        if query.season_number <= 1:
            return None

        previous_season = _find_season(anime, query.season_number - 1)
        if previous_season is None or not previous_season.episodes:
            return None

        last_episode = max(previous_season.episodes, key=lambda e: e.number.value)
        return EpisodeReferenceDTO(
            anime_id=query.anime_id,
            episode_id=str(last_episode.id),
            season_number=previous_season.number.value,
            episode_number=last_episode.number.value,
        )
