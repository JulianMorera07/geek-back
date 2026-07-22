"""Entidades del módulo de reproducción.

- `PlaybackSource` es una fuente de reproducción candidata (URL + calidad +
  audio + subtítulos disponibles desde un provider/servidor concreto).
- `EpisodePlayback` agrupa la metadata de un episodio con TODAS sus fuentes
  candidatas — es lo que arma un `SourceResolver` antes de que el usuario
  elija una.
- `PlaybackSession` es el Aggregate Root: una sesión de reproducción
  anónima que registra qué fuente/calidad/subtítulo se eligió y el
  progreso, con las transiciones de estado válidas de una reproducción.
"""

from __future__ import annotations

from datetime import UTC, datetime

from geekbaku.domain.catalog.value_objects import EpisodeId, Language, StreamQuality, VideoUrl
from geekbaku.domain.playback.exceptions import (
    InvalidSessionTransitionError,
    SourceNotFoundError,
)
from geekbaku.domain.playback.value_objects import (
    AudioTrack,
    PlaybackMetadata,
    PlaybackProvider,
    PlaybackSessionId,
    PlaybackSessionStatus,
    PlaybackSourceId,
    StreamingServer,
    Subtitle,
    WatchProgress,
)


class PlaybackSource:
    """Una fuente de reproducción candidata para un episodio."""

    def __init__(
        self,
        id: PlaybackSourceId,
        provider: PlaybackProvider,
        streaming_server: StreamingServer,
        url: VideoUrl,
        quality: StreamQuality,
        audio_track: AudioTrack,
        subtitles: tuple[Subtitle, ...] = (),
        is_active: bool = True,
        expires_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.provider = provider
        self.streaming_server = streaming_server
        self.url = url
        self.quality = quality
        self.audio_track = audio_track
        self.subtitles = subtitles
        self.is_active = is_active
        self.expires_at = expires_at

    def is_expired(self, *, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or datetime.now(UTC)) >= self.expires_at

    def is_available(self, *, now: datetime | None = None) -> bool:
        return self.is_active and not self.is_expired(now=now)

    def deactivate(self) -> None:
        self.is_active = False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PlaybackSource) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class EpisodePlayback:
    """Agrupa la metadata de un episodio con todas sus fuentes candidatas."""

    def __init__(
        self,
        episode_id: EpisodeId,
        metadata: PlaybackMetadata,
        sources: tuple[PlaybackSource, ...] = (),
    ) -> None:
        self.episode_id = episode_id
        self.metadata = metadata
        self._sources = list(sources)

    @property
    def sources(self) -> tuple[PlaybackSource, ...]:
        return tuple(self._sources)

    @property
    def available_sources(self) -> tuple[PlaybackSource, ...]:
        return tuple(s for s in self._sources if s.is_available())

    def add_source(self, source: PlaybackSource) -> None:
        self._sources.append(source)

    def get_source(self, source_id: PlaybackSourceId) -> PlaybackSource:
        for source in self._sources:
            if source.id == source_id:
                return source
        raise SourceNotFoundError(f"No existe la fuente {source_id} en este episodio.")

    def available_qualities(self) -> tuple[StreamQuality, ...]:
        seen: dict[StreamQuality, None] = {}
        for source in self.available_sources:
            seen.setdefault(source.quality, None)
        return tuple(seen.keys())


#: Transiciones de `PlaybackSessionStatus` permitidas.
_ALLOWED_SESSION_TRANSITIONS: dict[PlaybackSessionStatus, frozenset[PlaybackSessionStatus]] = {
    PlaybackSessionStatus.ACTIVE: frozenset(
        {
            PlaybackSessionStatus.PAUSED,
            PlaybackSessionStatus.COMPLETED,
            PlaybackSessionStatus.ABANDONED,
        }
    ),
    PlaybackSessionStatus.PAUSED: frozenset(
        {
            PlaybackSessionStatus.ACTIVE,
            PlaybackSessionStatus.COMPLETED,
            PlaybackSessionStatus.ABANDONED,
        }
    ),
    PlaybackSessionStatus.COMPLETED: frozenset(),
    PlaybackSessionStatus.ABANDONED: frozenset({PlaybackSessionStatus.ACTIVE}),
}


class PlaybackSession:
    """Aggregate Root: una sesión de reproducción anónima.

    Anónima a propósito (sin `user_id`, ver módulo docstring): no hay
    autenticación todavía. Se identifica y se recupera solo por su propio
    `PlaybackSessionId`.
    """

    def __init__(
        self,
        id: PlaybackSessionId,
        episode_id: EpisodeId,
        status: PlaybackSessionStatus = PlaybackSessionStatus.ACTIVE,
        selected_source_id: PlaybackSourceId | None = None,
        selected_quality: StreamQuality | None = None,
        selected_subtitle_language: Language | None = None,
        progress: WatchProgress | None = None,
        started_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.episode_id = episode_id
        self.status = status
        self.selected_source_id = selected_source_id
        self.selected_quality = selected_quality
        self.selected_subtitle_language = selected_subtitle_language
        self.progress = progress
        self.started_at = started_at or datetime.now(UTC)
        self.updated_at = updated_at or self.started_at

    def select_source(self, source_id: PlaybackSourceId) -> None:
        self.selected_source_id = source_id
        self._touch()

    def select_quality(self, quality: StreamQuality) -> None:
        self.selected_quality = quality
        self._touch()

    def select_subtitle(self, language: Language | None) -> None:
        """`None` significa "sin subtítulos" (elección explícita, no falta
        de selección: ver `SelectPlaybackSubtitle`)."""
        self.selected_subtitle_language = language
        self._touch()

    def update_progress(self, progress: WatchProgress) -> None:
        self.progress = progress
        self._touch()

    def pause(self) -> None:
        self._transition_to(PlaybackSessionStatus.PAUSED)

    def resume(self) -> None:
        self._transition_to(PlaybackSessionStatus.ACTIVE)

    def complete(self) -> None:
        self._transition_to(PlaybackSessionStatus.COMPLETED)

    def abandon(self) -> None:
        self._transition_to(PlaybackSessionStatus.ABANDONED)

    def _transition_to(self, new_status: PlaybackSessionStatus) -> None:
        if new_status == self.status:
            return
        allowed = _ALLOWED_SESSION_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise InvalidSessionTransitionError(
                f"No se puede pasar de estado '{self.status}' a '{new_status}'."
            )
        self.status = new_status
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PlaybackSession) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
