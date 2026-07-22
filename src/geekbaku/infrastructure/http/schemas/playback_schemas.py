"""Schemas Pydantic del Playback API. Se traducen a/desde los DTOs de
`application/playback/dto.py` en el router — nunca se pasan DTOs
directamente a FastAPI ni Pydantic models a los casos de uso.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SubtitleSchema(BaseModel):
    language_code: str
    format: str
    url: str | None
    is_default: bool


class AudioTrackSchema(BaseModel):
    language_code: str
    is_default: bool


class PlaybackSourceSchema(BaseModel):
    id: str
    provider_id: str
    server_name: str
    url: str
    quality: str
    audio: AudioTrackSchema
    subtitles: tuple[SubtitleSchema, ...]
    is_active: bool


class PlaybackMetadataSchema(BaseModel):
    title: str
    anime_title: str
    season_number: int
    episode_number: int
    duration_seconds: int | None
    thumbnail_url: str | None


class EpisodePlaybackSchema(BaseModel):
    episode_id: str
    metadata: PlaybackMetadataSchema
    sources: tuple[PlaybackSourceSchema, ...]
    available_qualities: tuple[str, ...]


class ResumePointSchema(BaseModel):
    position_seconds: int
    is_completed: bool


class WatchProgressSchema(BaseModel):
    position_seconds: int
    duration_seconds: int
    percentage: float
    updated_at: datetime


class PlaybackSessionSchema(BaseModel):
    id: str
    episode_id: str
    status: str
    selected_source_id: str | None
    selected_quality: str | None
    selected_subtitle_language_code: str | None
    progress: WatchProgressSchema | None
    started_at: datetime
    updated_at: datetime


class EpisodeReferenceSchema(BaseModel):
    anime_id: str
    episode_id: str
    season_number: int
    episode_number: int


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    episode_id: str


class SelectSourceRequest(BaseModel):
    source_id: str


class SelectQualityRequest(BaseModel):
    quality: str


class SelectSubtitleRequest(BaseModel):
    language_code: str | None = None
    language_name: str | None = None


class SaveProgressRequest(BaseModel):
    position_seconds: int
    duration_seconds: int
