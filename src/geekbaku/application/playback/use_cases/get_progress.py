"""Caso de uso: obtener el progreso de reproducción de una sesión.

Nunca se cachea: siempre se lee directo de `PlaybackSessionRepository`.
"""

from __future__ import annotations

from geekbaku.application.playback.dto import WatchProgressDTO
from geekbaku.application.playback.mappers import parse_playback_session_id, watch_progress_to_dto
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError


class GetWatchProgress:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, session_id: str) -> WatchProgressDTO | None:
        parsed_id = parse_playback_session_id(session_id)
        session = await self._sessions.get_by_id(parsed_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {parsed_id}.")

        return watch_progress_to_dto(session.progress) if session.progress else None
