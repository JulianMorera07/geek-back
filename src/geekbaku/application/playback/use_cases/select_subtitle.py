"""Caso de uso: seleccionar el idioma de subtítulos para la sesión activa.

Sin `language_code`/`language_name`, selecciona "sin subtítulos"
explícitamente (distinto de no haber seleccionado nada todavía).
"""

from __future__ import annotations

from geekbaku.application.playback.dto import PlaybackSessionDTO, SelectSubtitleCommand
from geekbaku.application.playback.mappers import (
    parse_playback_session_id,
    parse_subtitle_language,
    playback_session_to_dto,
)
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError


class SelectPlaybackSubtitle:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, command: SelectSubtitleCommand) -> PlaybackSessionDTO:
        session_id = parse_playback_session_id(command.session_id)
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {session_id}.")

        language = parse_subtitle_language(command.language_code, command.language_name)
        session.select_subtitle(language)
        await self._sessions.update(session)
        return playback_session_to_dto(session)
