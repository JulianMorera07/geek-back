"""Caso de uso: obtener los subtítulos disponibles para un episodio, sin
duplicados (varias fuentes pueden ofrecer el mismo idioma).
"""

from __future__ import annotations

from geekbaku.application.playback.dto import GetEpisodePlaybackQuery, SubtitleDTO
from geekbaku.application.playback.use_cases.get_episode_playback import GetEpisodePlayback


class GetAvailableSubtitles:
    def __init__(self, get_episode_playback: GetEpisodePlayback) -> None:
        self._get_episode_playback = get_episode_playback

    async def execute(self, query: GetEpisodePlaybackQuery) -> tuple[SubtitleDTO, ...]:
        episode_playback = await self._get_episode_playback.execute(query)
        seen: dict[tuple[str, str | None], SubtitleDTO] = {}
        for source in episode_playback.sources:
            for subtitle in source.subtitles:
                seen.setdefault((subtitle.language_code, subtitle.url), subtitle)
        return tuple(seen.values())
