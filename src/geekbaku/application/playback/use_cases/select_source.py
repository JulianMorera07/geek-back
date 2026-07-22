"""Caso de uso: seleccionar una fuente de reproducción para la sesión activa.

No revalida que `source_id` exista entre las fuentes disponibles del
episodio (eso requeriría volver a resolverlas contra el catálogo): se
confía en que el cliente elige entre lo que ya le devolvió
`GetPlaybackSources` para esa misma sesión, igual que otros casos de uso
del proyecto no revalidan referencias cruzadas ya vistas por el llamador
(ver `catalog.CreateAnime`).
"""

from __future__ import annotations

from geekbaku.application.playback.dto import PlaybackSessionDTO, SelectSourceCommand
from geekbaku.application.playback.mappers import (
    parse_playback_session_id,
    parse_playback_source_id,
    playback_session_to_dto,
)
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError


class SelectPlaybackSource:
    def __init__(self, sessions: PlaybackSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, command: SelectSourceCommand) -> PlaybackSessionDTO:
        session_id = parse_playback_session_id(command.session_id)
        session = await self._sessions.get_by_id(session_id)
        if session is None:
            raise PlaybackSessionNotFoundError(f"No existe la sesión {session_id}.")

        session.select_source(parse_playback_source_id(command.source_id))
        await self._sessions.update(session)
        return playback_session_to_dto(session)
