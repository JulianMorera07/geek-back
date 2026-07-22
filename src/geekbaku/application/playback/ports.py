"""Puertos del módulo de reproducción."""

from __future__ import annotations

from typing import Protocol

from geekbaku.domain.playback.entities import PlaybackSession
from geekbaku.domain.playback.value_objects import PlaybackSessionId


class PlaybackSessionRepository(Protocol):
    """Persiste `PlaybackSession` (progreso incluido). Nunca se cachea (ver
    `application/playback/cache.py`): siempre se lee/escribe directo acá.
    """

    async def get_by_id(self, session_id: PlaybackSessionId) -> PlaybackSession | None: ...

    async def add(self, session: PlaybackSession) -> None: ...

    async def update(self, session: PlaybackSession) -> None: ...
