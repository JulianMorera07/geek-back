"""Mappers del módulo de reproducción.

Traduce en ambas direcciones entre:
- El catálogo interno (`domain.catalog`, ya confiable/normalizado) y el
  dominio de reproducción (`domain.playback`) — `to_playback_source`,
  `to_playback_metadata`.
- El dominio de reproducción y los DTOs de salida/entrada de esta capa.

Reusa los `parse_*` de `application.catalog.mappers` para ids/enums
compartidos (AnimeId, EpisodeId, StreamQuality) en vez de duplicarlos.
"""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from geekbaku.application.playback.dto import (
    AudioTrackDTO,
    EpisodePlaybackDTO,
    PlaybackMetadataDTO,
    PlaybackSessionDTO,
    PlaybackSourceDTO,
    ResumePointDTO,
    SubtitleDTO,
    WatchProgressDTO,
)
from geekbaku.domain.catalog.entities import Anime, Episode, Season, StreamingSource
from geekbaku.domain.catalog.value_objects import Language
from geekbaku.domain.playback.entities import EpisodePlayback, PlaybackSession, PlaybackSource
from geekbaku.domain.playback.value_objects import (
    AudioTrack,
    PlaybackMetadata,
    PlaybackProvider,
    PlaybackSessionId,
    PlaybackSourceId,
    ResumePoint,
    StreamingServer,
    Subtitle,
    SubtitleFormat,
    SubtitleUrl,
    WatchProgress,
)
from geekbaku.domain.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Parsing: primitivos -> Value Objects
# ---------------------------------------------------------------------------


def _parse_uuid(value: str, *, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError(f"'{value}' no es un UUID válido para '{field_name}'.") from exc


def parse_playback_session_id(value: str) -> PlaybackSessionId:
    return PlaybackSessionId(_parse_uuid(value, field_name="session_id"))


def parse_playback_source_id(value: str) -> PlaybackSourceId:
    return PlaybackSourceId(_parse_uuid(value, field_name="source_id"))


# ---------------------------------------------------------------------------
# Catálogo interno -> dominio de reproducción
# ---------------------------------------------------------------------------


def to_playback_source(
    streaming_source: StreamingSource, provider_priority: int = 0
) -> PlaybackSource | None:
    """Convierte un `catalog.StreamingSource` persistido a un
    `playback.PlaybackSource` reproducible.

    Devuelve `None` si el `StreamingSource` todavía no tiene una `url`
    resuelta (existe la referencia al provider, pero no un enlace
    reproducible todavía) — resolverla dinámicamente contra el Provider
    Framework en el momento de reproducir queda para un sprint futuro (no
    hay ningún método en `ProviderPort` para eso todavía); este mapper solo
    puede trabajar con lo que ya está persistido.
    """
    if streaming_source.url is None:
        return None

    parsed_url = urlparse(streaming_source.url.value)
    server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    subtitles: tuple[Subtitle, ...] = ()
    if streaming_source.subtitle_language is not None:
        subtitles = (
            Subtitle(
                language=streaming_source.subtitle_language,
                format=SubtitleFormat.VTT,
                url=None,
                is_default=True,
            ),
        )

    return PlaybackSource(
        id=PlaybackSourceId(streaming_source.id.value),
        provider=PlaybackProvider(
            provider_id=streaming_source.provider_name, priority=provider_priority
        ),
        streaming_server=StreamingServer(
            name=streaming_source.provider_name, base_url=server_base_url
        ),
        url=streaming_source.url,
        quality=streaming_source.quality,
        audio_track=AudioTrack(language=streaming_source.audio_language, is_default=True),
        subtitles=subtitles,
        is_active=streaming_source.is_active,
    )


def to_playback_metadata(anime: Anime, season: Season, episode: Episode) -> PlaybackMetadata:
    return PlaybackMetadata(
        title=str(episode.title),
        anime_title=str(anime.title),
        season_number=season.number.value,
        episode_number=episode.number.value,
        duration_seconds=(episode.duration.minutes * 60) if episode.duration else None,
        thumbnail_url=episode.thumbnail.url.value if episode.thumbnail else None,
    )


# ---------------------------------------------------------------------------
# Dominio de reproducción -> DTO
# ---------------------------------------------------------------------------


def subtitle_to_dto(subtitle: Subtitle) -> SubtitleDTO:
    return SubtitleDTO(
        language_code=subtitle.language.code,
        format=str(subtitle.format),
        url=str(subtitle.url) if subtitle.url else None,
        is_default=subtitle.is_default,
    )


def audio_track_to_dto(audio_track: AudioTrack) -> AudioTrackDTO:
    return AudioTrackDTO(language_code=audio_track.language.code, is_default=audio_track.is_default)


def playback_source_to_dto(source: PlaybackSource) -> PlaybackSourceDTO:
    return PlaybackSourceDTO(
        id=str(source.id),
        provider_id=source.provider.provider_id,
        server_name=source.streaming_server.name,
        url=source.url.value,
        quality=str(source.quality),
        audio=audio_track_to_dto(source.audio_track),
        subtitles=tuple(subtitle_to_dto(s) for s in source.subtitles),
        is_active=source.is_active,
    )


def playback_metadata_to_dto(metadata: PlaybackMetadata) -> PlaybackMetadataDTO:
    return PlaybackMetadataDTO(
        title=metadata.title,
        anime_title=metadata.anime_title,
        season_number=metadata.season_number,
        episode_number=metadata.episode_number,
        duration_seconds=metadata.duration_seconds,
        thumbnail_url=metadata.thumbnail_url,
    )


def episode_playback_to_dto(episode_playback: EpisodePlayback) -> EpisodePlaybackDTO:
    return EpisodePlaybackDTO(
        episode_id=str(episode_playback.episode_id),
        metadata=playback_metadata_to_dto(episode_playback.metadata),
        sources=tuple(playback_source_to_dto(s) for s in episode_playback.available_sources),
        available_qualities=tuple(str(q) for q in episode_playback.available_qualities()),
    )


def resume_point_to_dto(resume_point: ResumePoint) -> ResumePointDTO:
    return ResumePointDTO(
        position_seconds=resume_point.position_seconds, is_completed=resume_point.is_completed
    )


def watch_progress_to_dto(progress: WatchProgress) -> WatchProgressDTO:
    return WatchProgressDTO(
        position_seconds=progress.position_seconds,
        duration_seconds=progress.duration_seconds,
        percentage=progress.percentage,
        updated_at=progress.updated_at,
    )


def playback_session_to_dto(session: PlaybackSession) -> PlaybackSessionDTO:
    return PlaybackSessionDTO(
        id=str(session.id),
        episode_id=str(session.episode_id),
        status=str(session.status),
        selected_source_id=str(session.selected_source_id) if session.selected_source_id else None,
        selected_quality=str(session.selected_quality) if session.selected_quality else None,
        selected_subtitle_language_code=(
            session.selected_subtitle_language.code if session.selected_subtitle_language else None
        ),
        progress=watch_progress_to_dto(session.progress) if session.progress else None,
        started_at=session.started_at,
        updated_at=session.updated_at,
    )


def parse_subtitle_language(code: str | None, name: str | None) -> Language | None:
    if code is None or name is None:
        return None
    return Language(code=code, name=name)


def parse_subtitle_url(value: str | None) -> SubtitleUrl | None:
    return SubtitleUrl(value) if value else None
