"""Caso de uso: crear una sesión de reproducción anónima para un episodio."""

from __future__ import annotations

from geekbaku.application.catalog.mappers import parse_episode_id
from geekbaku.application.playback.dto import CreatePlaybackSessionCommand, PlaybackSessionDTO
from geekbaku.application.playback.mappers import playback_session_to_dto
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.entities import PlaybackSession
from geekbaku.domain.playback.value_objects import PlaybackSessionId


class CreatePlaybackSession:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, command: CreatePlaybackSessionCommand) -> PlaybackSessionDTO:
        episode_id = parse_episode_id(command.episode_id)
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=episode_id)
        await self._sessions.add(session)
        return playback_session_to_dto(session)
