"""Caso de uso: obtener las fuentes de reproducción de un episodio."""

from __future__ import annotations

from geekbaku.application.playback.dto import GetEpisodePlaybackQuery, PlaybackSourceDTO
from geekbaku.application.playback.use_cases.get_episode_playback import GetEpisodePlayback


class GetPlaybackSources:
    def __init__(self, get_episode_playback: GetEpisodePlayback) -> None:
        self._get_episode_playback = get_episode_playback

    async def execute(self, query: GetEpisodePlaybackQuery) -> tuple[PlaybackSourceDTO, ...]:
        episode_playback = await self._get_episode_playback.execute(query)
        return episode_playback.sources
