"""Caso de uso: seleccionar la calidad de video para la sesión activa."""

from __future__ import annotations

from geekbaku.application.catalog.mappers import parse_stream_quality
from geekbaku.application.playback.dto import PlaybackSessionDTO, SelectQualityCommand
from geekbaku.application.playback.mappers import parse_playback_session_id, playback_session_to_dto
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError


class SelectPlaybackQuality:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, command: SelectQualityCommand) -> PlaybackSessionDTO:
        session_id = parse_playback_session_id(command.session_id)
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {session_id}.")

        session.select_quality(parse_stream_quality(command.quality))
        await self._sessions.update(session)
        return playback_session_to_dto(session)
