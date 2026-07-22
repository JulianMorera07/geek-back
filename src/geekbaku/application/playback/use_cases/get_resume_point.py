"""Caso de uso: obtener el punto de reanudación de una sesión."""

from __future__ import annotations

from geekbaku.application.playback.dto import ResumePointDTO
from geekbaku.application.playback.mappers import parse_playback_session_id, resume_point_to_dto
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError
from geekbaku.domain.playback.services import ResumePointService


class GetResumePoint:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, session_id: str) -> ResumePointDTO:
        parsed_id = parse_playback_session_id(session_id)
        session = await self._sessions.get_by_id(parsed_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {parsed_id}.")

        resume_point = ResumePointService.compute(session.progress)
        return resume_point_to_dto(resume_point)
