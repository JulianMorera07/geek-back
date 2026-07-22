"""Playback API: endpoints para preparar y controlar la reproducción de un
episodio. Cada handler traduce Schema -> DTO/Command -> caso de uso -> DTO
-> Schema; ningún caso de uso conoce FastAPI ni Pydantic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geekbaku.application.playback.dto import (
    AdjacentEpisodeQuery,
    CreatePlaybackSessionCommand,
    GetEpisodePlaybackQuery,
    SaveProgressCommand,
    SelectQualityCommand,
    SelectSourceCommand,
    SelectSubtitleCommand,
)
from geekbaku.application.playback.use_cases.create_session import CreatePlaybackSession
from geekbaku.application.playback.use_cases.get_episode_playback import GetEpisodePlayback
from geekbaku.application.playback.use_cases.get_next_episode import GetNextEpisode
from geekbaku.application.playback.use_cases.get_previous_episode import GetPreviousEpisode
from geekbaku.application.playback.use_cases.get_progress import GetWatchProgress
from geekbaku.application.playback.use_cases.get_qualities import GetAvailableQualities
from geekbaku.application.playback.use_cases.get_resume_point import GetResumePoint
from geekbaku.application.playback.use_cases.get_sources import GetPlaybackSources
from geekbaku.application.playback.use_cases.get_subtitles import GetAvailableSubtitles
from geekbaku.application.playback.use_cases.save_progress import SaveWatchProgress
from geekbaku.application.playback.use_cases.select_quality import SelectPlaybackQuality
from geekbaku.application.playback.use_cases.select_source import SelectPlaybackSource
from geekbaku.application.playback.use_cases.select_subtitle import SelectPlaybackSubtitle
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.playback_schemas import (
    CreateSessionRequest,
    EpisodePlaybackSchema,
    EpisodeReferenceSchema,
    PlaybackSessionSchema,
    PlaybackSourceSchema,
    ResumePointSchema,
    SaveProgressRequest,
    SelectQualityRequest,
    SelectSourceRequest,
    SelectSubtitleRequest,
    SubtitleSchema,
    WatchProgressSchema,
)

router = APIRouter(tags=["playback"])


# ---------------------------------------------------------------------------
# Episodio: metadata + fuentes + subtítulos + calidades
# ---------------------------------------------------------------------------


@router.get("/animes/{anime_id}/episodes/{episode_id}/playback")
async def get_episode_playback(
    anime_id: str,
    episode_id: str,
    preferred_quality: str | None = None,
    use_case: GetEpisodePlayback = Depends(deps.get_episode_playback_use_case),
) -> EpisodePlaybackSchema:
    result = await use_case.execute(
        GetEpisodePlaybackQuery(
            anime_id=anime_id, episode_id=episode_id, preferred_quality=preferred_quality
        )
    )
    return EpisodePlaybackSchema.model_validate(result, from_attributes=True)


@router.get("/animes/{anime_id}/episodes/{episode_id}/playback/sources")
async def get_playback_sources(
    anime_id: str,
    episode_id: str,
    use_case: GetPlaybackSources = Depends(deps.get_playback_sources_use_case),
) -> list[PlaybackSourceSchema]:
    sources = await use_case.execute(
        GetEpisodePlaybackQuery(anime_id=anime_id, episode_id=episode_id)
    )
    return [PlaybackSourceSchema.model_validate(s, from_attributes=True) for s in sources]


@router.get("/animes/{anime_id}/episodes/{episode_id}/playback/subtitles")
async def get_playback_subtitles(
    anime_id: str,
    episode_id: str,
    use_case: GetAvailableSubtitles = Depends(deps.get_available_subtitles_use_case),
) -> list[SubtitleSchema]:
    subtitles = await use_case.execute(
        GetEpisodePlaybackQuery(anime_id=anime_id, episode_id=episode_id)
    )
    return [SubtitleSchema.model_validate(s, from_attributes=True) for s in subtitles]


@router.get("/animes/{anime_id}/episodes/{episode_id}/playback/qualities")
async def get_playback_qualities(
    anime_id: str,
    episode_id: str,
    use_case: GetAvailableQualities = Depends(deps.get_available_qualities_use_case),
) -> list[str]:
    qualities = await use_case.execute(
        GetEpisodePlaybackQuery(anime_id=anime_id, episode_id=episode_id)
    )
    return list(qualities)


# ---------------------------------------------------------------------------
# Navegación entre episodios
# ---------------------------------------------------------------------------


@router.get("/animes/{anime_id}/seasons/{season_number}/episodes/{episode_number}/next")
async def get_next_episode(
    anime_id: str,
    season_number: int,
    episode_number: int,
    use_case: GetNextEpisode = Depends(deps.get_next_episode_use_case),
) -> EpisodeReferenceSchema | None:
    result = await use_case.execute(
        AdjacentEpisodeQuery(
            anime_id=anime_id, season_number=season_number, episode_number=episode_number
        )
    )
    return EpisodeReferenceSchema.model_validate(result, from_attributes=True) if result else None


@router.get("/animes/{anime_id}/seasons/{season_number}/episodes/{episode_number}/previous")
async def get_previous_episode(
    anime_id: str,
    season_number: int,
    episode_number: int,
    use_case: GetPreviousEpisode = Depends(deps.get_previous_episode_use_case),
) -> EpisodeReferenceSchema | None:
    result = await use_case.execute(
        AdjacentEpisodeQuery(
            anime_id=anime_id, season_number=season_number, episode_number=episode_number
        )
    )
    return EpisodeReferenceSchema.model_validate(result, from_attributes=True) if result else None


# ---------------------------------------------------------------------------
# Sesiones de reproducción y progreso
# ---------------------------------------------------------------------------


@router.post("/playback/sessions", status_code=201)
async def create_playback_session(
    body: CreateSessionRequest,
    use_case: CreatePlaybackSession = Depends(deps.get_create_playback_session_use_case),
) -> PlaybackSessionSchema:
    result = await use_case.execute(CreatePlaybackSessionCommand(episode_id=body.episode_id))
    return PlaybackSessionSchema.model_validate(result, from_attributes=True)


@router.post("/playback/sessions/{session_id}/source")
async def select_playback_source(
    session_id: str,
    body: SelectSourceRequest,
    use_case: SelectPlaybackSource = Depends(deps.get_select_playback_source_use_case),
) -> PlaybackSessionSchema:
    result = await use_case.execute(
        SelectSourceCommand(session_id=session_id, source_id=body.source_id)
    )
    return PlaybackSessionSchema.model_validate(result, from_attributes=True)


@router.post("/playback/sessions/{session_id}/quality")
async def select_playback_quality(
    session_id: str,
    body: SelectQualityRequest,
    use_case: SelectPlaybackQuality = Depends(deps.get_select_playback_quality_use_case),
) -> PlaybackSessionSchema:
    result = await use_case.execute(
        SelectQualityCommand(session_id=session_id, quality=body.quality)
    )
    return PlaybackSessionSchema.model_validate(result, from_attributes=True)


@router.post("/playback/sessions/{session_id}/subtitle")
async def select_playback_subtitle(
    session_id: str,
    body: SelectSubtitleRequest,
    use_case: SelectPlaybackSubtitle = Depends(deps.get_select_playback_subtitle_use_case),
) -> PlaybackSessionSchema:
    result = await use_case.execute(
        SelectSubtitleCommand(
            session_id=session_id,
            language_code=body.language_code,
            language_name=body.language_name,
        )
    )
    return PlaybackSessionSchema.model_validate(result, from_attributes=True)


@router.post("/playback/sessions/{session_id}/progress")
async def save_playback_progress(
    session_id: str,
    body: SaveProgressRequest,
    use_case: SaveWatchProgress = Depends(deps.get_save_watch_progress_use_case),
) -> PlaybackSessionSchema:
    result = await use_case.execute(
        SaveProgressCommand(
            session_id=session_id,
            position_seconds=body.position_seconds,
            duration_seconds=body.duration_seconds,
        )
    )
    return PlaybackSessionSchema.model_validate(result, from_attributes=True)


@router.get("/playback/sessions/{session_id}/progress")
async def get_playback_progress(
    session_id: str,
    use_case: GetWatchProgress = Depends(deps.get_watch_progress_use_case),
) -> WatchProgressSchema | None:
    result = await use_case.execute(session_id)
    return WatchProgressSchema.model_validate(result, from_attributes=True) if result else None


@router.get("/playback/sessions/{session_id}/resume-point")
async def get_playback_resume_point(
    session_id: str,
    use_case: GetResumePoint = Depends(deps.get_resume_point_use_case),
) -> ResumePointSchema:
    result = await use_case.execute(session_id)
    return ResumePointSchema.model_validate(result, from_attributes=True)
