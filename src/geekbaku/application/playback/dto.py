"""DTOs del módulo de reproducción.

`dataclasses` puros (no Pydantic), igual que el resto de `application/*`:
los schemas Pydantic viven en `infrastructure/http/schemas`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubtitleDTO:
    language_code: str
    format: str
    url: str | None
    is_default: bool


@dataclass(frozen=True, slots=True)
class AudioTrackDTO:
    language_code: str
    is_default: bool


@dataclass(frozen=True, slots=True)
class PlaybackSourceDTO:
    id: str
    provider_id: str
    server_name: str
    url: str
    quality: str
    audio: AudioTrackDTO
    subtitles: tuple[SubtitleDTO, ...] = field(default_factory=tuple)
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class PlaybackMetadataDTO:
    title: str
    anime_title: str
    season_number: int
    episode_number: int
    duration_seconds: int | None
    thumbnail_url: str | None


@dataclass(frozen=True, slots=True)
class EpisodePlaybackDTO:
    episode_id: str
    metadata: PlaybackMetadataDTO
    sources: tuple[PlaybackSourceDTO, ...]
    available_qualities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResumePointDTO:
    position_seconds: int
    is_completed: bool


@dataclass(frozen=True, slots=True)
class WatchProgressDTO:
    position_seconds: int
    duration_seconds: int
    percentage: float
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlaybackSessionDTO:
    id: str
    episode_id: str
    status: str
    selected_source_id: str | None
    selected_quality: str | None
    selected_subtitle_language_code: str | None
    progress: WatchProgressDTO | None
    started_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EpisodeReferenceDTO:
    anime_id: str
    episode_id: str
    season_number: int
    episode_number: int


# ---------------------------------------------------------------------------
# Commands / Queries
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreatePlaybackSessionCommand:
    episode_id: str


@dataclass(frozen=True, slots=True)
class SelectSourceCommand:
    session_id: str
    source_id: str


@dataclass(frozen=True, slots=True)
class SelectQualityCommand:
    session_id: str
    quality: str


@dataclass(frozen=True, slots=True)
class SelectSubtitleCommand:
    session_id: str
    language_code: str | None = None
    language_name: str | None = None


@dataclass(frozen=True, slots=True)
class SaveProgressCommand:
    session_id: str
    position_seconds: int
    duration_seconds: int


@dataclass(frozen=True, slots=True)
class GetEpisodePlaybackQuery:
    """`anime_id` es requerido: ninguno de nuestros repositorios soporta
    buscar "a qué Anime/Season pertenece este episodio" solo a partir de un
    `episode_id` (`EpisodeRepository.get_by_id` devuelve el `Episode`
    aislado, sin contexto) — el llamador ya lo conoce porque llegó
    navegando desde el catálogo (anime -> season -> episodio).
    """

    anime_id: str
    episode_id: str
    preferred_quality: str | None = None
    preferred_provider_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class AdjacentEpisodeQuery:
    anime_id: str
    season_number: int
    episode_number: int
