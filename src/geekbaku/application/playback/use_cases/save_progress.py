"""Caso de uso: guardar el progreso de reproducción de la sesión activa.

Nunca se cachea (a diferencia de la metadata en `GetEpisodePlayback`):
siempre se escribe directo en `PlaybackSessionRepository`. Si el progreso
llega cerca del final del episodio, la sesión se marca `COMPLETED`
automáticamente (misma regla que usa `ResumePointService` para decidir
cuándo reanudar desde 0).
"""

from __future__ import annotations

from geekbaku.application.playback.dto import PlaybackSessionDTO, SaveProgressCommand
from geekbaku.application.playback.mappers import parse_playback_session_id, playback_session_to_dto
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError
from geekbaku.domain.playback.services import ResumePointService
from geekbaku.domain.playback.value_objects import PlaybackSessionStatus, WatchProgress


class SaveWatchProgress:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, command: SaveProgressCommand) -> PlaybackSessionDTO:
        session_id = parse_playback_session_id(command.session_id)
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {session_id}.")

        progress = WatchProgress.at(command.position_seconds, command.duration_seconds)
        session.update_progress(progress)

        resume_point = ResumePointService.compute(progress)
        if resume_point.is_completed and session.status == PlaybackSessionStatus.ACTIVE:
            session.complete()

        await self._sessions.update(session)
        return playback_session_to_dto(session)
