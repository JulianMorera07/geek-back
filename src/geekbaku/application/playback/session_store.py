"""Implementación de referencia de `PlaybackSessionRepository`.

Como las sesiones son anónimas (sin `user_id`, no hay autenticación
todavía) y de vida corta, un store in-memory de un solo proceso es una
implementación razonable por defecto — no un doble de test. Un backend
distribuido (Redis, para que sobreviva a reinicios/múltiples instancias del
proceso) es un adapter futuro que implementa el mismo `PlaybackSessionRepository`
sin tocar ningún caso de uso.
"""

from __future__ import annotations

from geekbaku.domain.playback.entities import PlaybackSession
from geekbaku.domain.playback.value_objects import PlaybackSessionId


class InMemoryPlaybackSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[PlaybackSessionId, PlaybackSession] = {}

    async def get_by_id(self, session_id: PlaybackSessionId) -> PlaybackSession | None:
        return self._sessions.get(session_id)

    async def add(self, session: PlaybackSession) -> None:
        self._sessions[session.id] = session

    async def update(self, session: PlaybackSession) -> None:
        self._sessions[session.id] = session
