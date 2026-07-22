"""Helper compartido: ubicar la Season que contiene un Episode dentro de un
Anime ya cargado. Ningún repositorio soporta "a qué Season pertenece este
episodio" directo (`EpisodeRepository.get_by_id` devuelve el `Episode`
aislado, sin contexto) — los casos de uso de reproducción necesitan ambos
(la Season, para `season_number`; el Episode, para todo lo demás), así que
recorren las temporadas del `Anime` una vez.
"""

from __future__ import annotations

from geekbaku.domain.catalog.entities import Anime, Episode, Season
from geekbaku.domain.catalog.exceptions import EpisodeNotFoundError
from geekbaku.domain.catalog.value_objects import EpisodeId


def find_season_and_episode(anime: Anime, episode_id: EpisodeId) -> tuple[Season, Episode]:
    for season in anime.seasons:
        for episode in season.episodes:
            if episode.id == episode_id:
                return season, episode
    raise EpisodeNotFoundError(f"No existe el episodio {episode_id} en el anime {anime.id}.")
