"""Caso de uso: obtener la referencia al siguiente episodio.

Si el episodio actual es el último de la temporada, continúa en el primer
episodio de la siguiente temporada. Devuelve `None` si no hay siguiente
(fin de la serie) — mismo valor tanto para "no hay más episodios" como para
una `season_number`/`episode_number` que no existen: distinguir ambos
casos requeriría exponer un error de validación que el llamador no
necesita (ya conoce la temporada/episodio actual porque está reproduciendo).
"""

from __future__ import annotations

from geekbaku.application.catalog.mappers import parse_anime_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.playback.dto import AdjacentEpisodeQuery, EpisodeReferenceDTO
from geekbaku.domain.catalog.entities import Anime, Season
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


def _find_season(anime: Anime, season_number: int) -> Season | None:
    return next((s for s in anime.seasons if s.number.value == season_number), None)


class GetNextEpisode:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: AdjacentEpisodeQuery) -> EpisodeReferenceDTO | None:
        anime_id = parse_anime_id(query.anime_id)
        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
        if anime is None:
            raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

        current_season = _find_season(anime, query.season_number)
        if current_season is not None:
            next_in_season = next(
                (e for e in current_season.episodes if e.number.value == query.episode_number + 1),
                None,
            )
            if next_in_season is not None:
                return EpisodeReferenceDTO(
                    anime_id=query.anime_id,
                    episode_id=str(next_in_season.id),
                    season_number=current_season.number.value,
                    episode_number=next_in_season.number.value,
                )

        next_season = _find_season(anime, query.season_number + 1)
        if next_season is None or not next_season.episodes:
            return None

        first_episode = min(next_season.episodes, key=lambda e: e.number.value)
        return EpisodeReferenceDTO(
            anime_id=query.anime_id,
            episode_id=str(first_episode.id),
            season_number=next_season.number.value,
            episode_number=first_episode.number.value,
        )
