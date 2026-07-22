"""Caso de uso: obtener las calidades de video disponibles para un episodio."""

from __future__ import annotations

from geekbaku.application.playback.dto import GetEpisodePlaybackQuery
from geekbaku.application.playback.use_cases.get_episode_playback import GetEpisodePlayback


class GetAvailableQualities:
    def __init__(self, get_episode_playback: GetEpisodePlayback) -> None:
        self._get_episode_playback = get_episode_playback

    async def execute(self, query: GetEpisodePlaybackQuery) -> tuple[str, ...]:
        episode_playback = await self._get_episode_playback.execute(query)
        return episode_playback.available_qualities
