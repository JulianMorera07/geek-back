import pytest

from geekbaku.application.playback.dto import (
    AdjacentEpisodeQuery,
    CreatePlaybackSessionCommand,
    GetEpisodePlaybackQuery,
    SaveProgressCommand,
    SelectQualityCommand,
    SelectSourceCommand,
    SelectSubtitleCommand,
)
from geekbaku.application.playback.session_store import InMemoryPlaybackSessionRepository
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
from geekbaku.application.providers.cache import InMemoryProviderCache
from geekbaku.domain.catalog.entities import Anime, Episode, Season, StreamingSource
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    Language,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    Title,
    VideoUrl,
)
from geekbaku.domain.playback.exceptions import PlaybackSessionNotFoundError
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

JAPANESE = Language(code="ja", name="Japanese")


def make_streaming_source(number_suffix: str = "1") -> StreamingSource:
    return StreamingSource(
        id=StreamingSourceId.new(),
        provider_name="provider-a",
        external_ref=f"ep-{number_suffix}",
        quality=StreamQuality.HD,
        audio_language=JAPANESE,
        url=VideoUrl(f"https://cdn.example.com/ep{number_suffix}.m3u8"),
    )


def make_episode(number: int, with_source: bool = True) -> Episode:
    episode = Episode(
        id=EpisodeId.new(), number=EpisodeNumber(number), title=Title(f"Episode {number}")
    )
    if with_source:
        episode.add_streaming_source(make_streaming_source(str(number)))
    return episode


async def seed_anime(
    uow: FakeCatalogUnitOfWork, *, seasons_episodes: dict[int, list[int]]
) -> Anime:
    anime = Anime(
        id=AnimeId.new(),
        title=Title("Attack on Titan"),
        slug=Slug("attack-on-titan"),
        anime_type=AnimeType.TV,
    )
    for season_number, episode_numbers in seasons_episodes.items():
        season = Season(id=SeasonId.new(), number=SeasonNumber(season_number))
        for episode_number in episode_numbers:
            season.add_episode(make_episode(episode_number))
        anime.add_season(season)
    await uow.animes.add(anime)
    return anime


class TestGetEpisodePlayback:
    async def test_returns_episode_playback_with_sources(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1, 2]})
        episode_id = anime.seasons[0].episodes[0].id
        use_case = GetEpisodePlayback(uow)

        result = await use_case.execute(
            GetEpisodePlaybackQuery(anime_id=str(anime.id), episode_id=str(episode_id))
        )

        assert result.episode_id == str(episode_id)
        assert len(result.sources) == 1
        assert result.metadata.season_number == 1

    async def test_raises_when_anime_not_found(self) -> None:
        uow = FakeCatalogUnitOfWork()
        use_case = GetEpisodePlayback(uow)

        with pytest.raises(AnimeNotFoundError):
            await use_case.execute(
                GetEpisodePlaybackQuery(
                    anime_id=str(AnimeId.new()), episode_id=str(EpisodeId.new())
                )
            )

    async def test_caches_result(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        episode_id = anime.seasons[0].episodes[0].id
        cache = InMemoryProviderCache()
        use_case = GetEpisodePlayback(uow, cache=cache)
        query = GetEpisodePlaybackQuery(anime_id=str(anime.id), episode_id=str(episode_id))

        first = await use_case.execute(query)
        # borra el anime del uow: si la segunda llamada no viene de cache, fallaría
        uow.animes._animes.clear()  # type: ignore[attr-defined]
        second = await use_case.execute(query)

        assert first == second


class TestGetPlaybackSourcesQualitiesSubtitles:
    async def test_get_sources_returns_mapped_sources(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        episode_id = anime.seasons[0].episodes[0].id
        use_case = GetPlaybackSources(GetEpisodePlayback(uow))

        sources = await use_case.execute(
            GetEpisodePlaybackQuery(anime_id=str(anime.id), episode_id=str(episode_id))
        )

        assert len(sources) == 1

    async def test_get_qualities_returns_available_qualities(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        episode_id = anime.seasons[0].episodes[0].id
        use_case = GetAvailableQualities(GetEpisodePlayback(uow))

        qualities = await use_case.execute(
            GetEpisodePlaybackQuery(anime_id=str(anime.id), episode_id=str(episode_id))
        )

        assert qualities == ("hd",)

    async def test_get_subtitles_deduplicates(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        episode = anime.seasons[0].episodes[0]
        episode.add_streaming_source(
            StreamingSource(
                id=StreamingSourceId.new(),
                provider_name="provider-b",
                external_ref="ep-1-alt",
                quality=StreamQuality.SD,
                audio_language=JAPANESE,
                subtitle_language=Language(code="en", name="English"),
                url=VideoUrl("https://cdn.example.com/ep1-alt.m3u8"),
            )
        )
        use_case = GetAvailableSubtitles(GetEpisodePlayback(uow))

        subtitles = await use_case.execute(
            GetEpisodePlaybackQuery(anime_id=str(anime.id), episode_id=str(episode.id))
        )

        assert len(subtitles) == 1
        assert subtitles[0].language_code == "en"


class TestSessionLifecycle:
    async def test_create_select_and_save_progress(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        episode_id = EpisodeId.new()

        created = await CreatePlaybackSession(sessions).execute(
            CreatePlaybackSessionCommand(episode_id=str(episode_id))
        )
        assert created.status == "active"

        source_id = str(StreamingSourceId.new())
        after_source = await SelectPlaybackSource(sessions).execute(
            SelectSourceCommand(session_id=created.id, source_id=source_id)
        )
        assert after_source.selected_source_id == source_id

        after_quality = await SelectPlaybackQuality(sessions).execute(
            SelectQualityCommand(session_id=created.id, quality="fhd")
        )
        assert after_quality.selected_quality == "fhd"

        after_subtitle = await SelectPlaybackSubtitle(sessions).execute(
            SelectSubtitleCommand(
                session_id=created.id, language_code="en", language_name="English"
            )
        )
        assert after_subtitle.selected_subtitle_language_code == "en"

        after_progress = await SaveWatchProgress(sessions).execute(
            SaveProgressCommand(session_id=created.id, position_seconds=50, duration_seconds=100)
        )
        assert after_progress.progress is not None
        assert after_progress.progress.position_seconds == 50
        assert after_progress.status == "active"

    async def test_save_progress_near_end_marks_completed(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        created = await CreatePlaybackSession(sessions).execute(
            CreatePlaybackSessionCommand(episode_id=str(EpisodeId.new()))
        )

        result = await SaveWatchProgress(sessions).execute(
            SaveProgressCommand(session_id=created.id, position_seconds=98, duration_seconds=100)
        )

        assert result.status == "completed"

    async def test_select_source_raises_when_session_not_found(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        with pytest.raises(PlaybackSessionNotFoundError):
            await SelectPlaybackSource(sessions).execute(
                SelectSourceCommand(session_id=str(EpisodeId.new().value), source_id="whatever")
            )

    async def test_get_progress_returns_none_before_any_save(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        created = await CreatePlaybackSession(sessions).execute(
            CreatePlaybackSessionCommand(episode_id=str(EpisodeId.new()))
        )

        progress = await GetWatchProgress(sessions).execute(created.id)

        assert progress is None

    async def test_get_progress_raises_when_session_not_found(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        with pytest.raises(PlaybackSessionNotFoundError):
            await GetWatchProgress(sessions).execute(str(EpisodeId.new().value))

    async def test_get_resume_point_without_progress_starts_at_zero(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        created = await CreatePlaybackSession(sessions).execute(
            CreatePlaybackSessionCommand(episode_id=str(EpisodeId.new()))
        )

        resume_point = await GetResumePoint(sessions).execute(created.id)

        assert resume_point.position_seconds == 0
        assert resume_point.is_completed is False

    async def test_get_resume_point_reflects_saved_progress(self) -> None:
        sessions = InMemoryPlaybackSessionRepository()
        created = await CreatePlaybackSession(sessions).execute(
            CreatePlaybackSessionCommand(episode_id=str(EpisodeId.new()))
        )
        await SaveWatchProgress(sessions).execute(
            SaveProgressCommand(session_id=created.id, position_seconds=30, duration_seconds=100)
        )

        resume_point = await GetResumePoint(sessions).execute(created.id)

        assert resume_point.position_seconds == 30


class TestNextAndPreviousEpisode:
    async def test_next_episode_within_same_season(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1, 2]})
        use_case = GetNextEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=1, episode_number=1)
        )

        assert result is not None
        assert result.episode_number == 2
        assert result.season_number == 1

    async def test_next_episode_crosses_into_next_season(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1], 2: [1, 2]})
        use_case = GetNextEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=1, episode_number=1)
        )

        assert result is not None
        assert result.season_number == 2
        assert result.episode_number == 1

    async def test_next_episode_returns_none_at_end_of_series(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        use_case = GetNextEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=1, episode_number=1)
        )

        assert result is None

    async def test_next_episode_raises_when_anime_not_found(self) -> None:
        uow = FakeCatalogUnitOfWork()
        with pytest.raises(AnimeNotFoundError):
            await GetNextEpisode(uow).execute(
                AdjacentEpisodeQuery(anime_id=str(AnimeId.new()), season_number=1, episode_number=1)
            )

    async def test_previous_episode_within_same_season(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1, 2]})
        use_case = GetPreviousEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=1, episode_number=2)
        )

        assert result is not None
        assert result.episode_number == 1

    async def test_previous_episode_crosses_into_previous_season(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1, 2], 2: [1]})
        use_case = GetPreviousEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=2, episode_number=1)
        )

        assert result is not None
        assert result.season_number == 1
        assert result.episode_number == 2

    async def test_previous_episode_returns_none_at_start_of_series(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await seed_anime(uow, seasons_episodes={1: [1]})
        use_case = GetPreviousEpisode(uow)

        result = await use_case.execute(
            AdjacentEpisodeQuery(anime_id=str(anime.id), season_number=1, episode_number=1)
        )

        assert result is None
