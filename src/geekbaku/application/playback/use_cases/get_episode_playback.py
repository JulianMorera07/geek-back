"""Caso de uso: obtener metadata + fuentes de reproducción de un episodio
(Playback API: "Obtener episodio"). Cachea únicamente el resultado (todo
metadata: título, fuentes, calidades — nada específico de un usuario),
nunca progreso.
"""

from __future__ import annotations

import logging

from geekbaku.application.catalog.mappers import parse_anime_id, parse_episode_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.playback.catalog_lookup import find_season_and_episode
from geekbaku.application.playback.dto import EpisodePlaybackDTO, GetEpisodePlaybackQuery
from geekbaku.application.playback.mappers import episode_playback_to_dto
from geekbaku.application.playback.source_resolver import SourceResolver
from geekbaku.application.providers.cache import ProviderCache, build_cache_key
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError

logger = logging.getLogger("geekbaku.playback")

_DEFAULT_CACHE_TTL_SECONDS = 600.0


class GetEpisodePlayback:
    def __init__(
        self,
        uow: CatalogUnitOfWork,
        resolver: SourceResolver | None = None,
        cache: ProviderCache | None = None,
        cache_ttl_seconds: float = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._uow = uow
        self._resolver = resolver or SourceResolver()
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def execute(self, query: GetEpisodePlaybackQuery) -> EpisodePlaybackDTO:
        cache_key = build_cache_key("episode_playback", query.anime_id, query.episode_id)

        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                logger.debug("playback_metadata_cache_hit episode_id=%s", query.episode_id)
                return cached  # type: ignore[return-value]

        anime_id = parse_anime_id(query.anime_id)
        episode_id = parse_episode_id(query.episode_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
        if anime is None:
            raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

        season, episode = find_season_and_episode(anime, episode_id)
        episode_playback = self._resolver.resolve(anime, season, episode)
        dto = episode_playback_to_dto(episode_playback)

        if self._cache is not None:
            await self._cache.set(cache_key, dto, self._cache_ttl_seconds)

        logger.info(
            "playback_episode_resolved episode_id=%s sources=%d",
            query.episode_id,
            len(dto.sources),
        )
        return dto
