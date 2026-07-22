import pytest

from geekbaku.application.playback.source_resolver import SourceResolver
from geekbaku.domain.catalog.entities import Anime, Episode, Season, StreamingSource
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
from geekbaku.domain.playback.exceptions import NoAvailableSourceError

JAPANESE = Language(code="ja", name="Japanese")


def make_anime_season_episode(
    streaming_sources: list[StreamingSource],
) -> tuple[Anime, Season, Episode]:
    anime = Anime(
        id=AnimeId.new(),
        title=Title("Attack on Titan"),
        slug=Slug("attack-on-titan"),
        anime_type=AnimeType.TV,
    )
    season = Season(id=SeasonId.new(), number=SeasonNumber(1))
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    for source in streaming_sources:
        episode.add_streaming_source(source)
    season.add_episode(episode)
    anime.add_season(season)
    return anime, season, episode


def make_streaming_source(
    provider_name: str = "provider-a",
    quality: StreamQuality = StreamQuality.HD,
    url: str | None = "https://cdn.example.com/ep1.m3u8",
) -> StreamingSource:
    return StreamingSource(
        id=StreamingSourceId.new(),
        provider_name=provider_name,
        external_ref="ep-1",
        quality=quality,
        audio_language=JAPANESE,
        url=VideoUrl(url) if url else None,
    )


class TestResolve:
    def test_builds_episode_playback_with_mapped_sources(self) -> None:
        anime, season, episode = make_anime_season_episode([make_streaming_source()])
        resolver = SourceResolver()

        episode_playback = resolver.resolve(anime, season, episode)

        assert episode_playback.episode_id == episode.id
        assert len(episode_playback.sources) == 1
        assert episode_playback.metadata.anime_title == "Attack on Titan"

    def test_skips_sources_without_url(self) -> None:
        anime, season, episode = make_anime_season_episode([make_streaming_source(url=None)])
        resolver = SourceResolver()

        episode_playback = resolver.resolve(anime, season, episode)

        assert episode_playback.sources == ()

    def test_applies_provider_priorities(self) -> None:
        anime, season, episode = make_anime_season_episode(
            [make_streaming_source(provider_name="provider-a")]
        )
        resolver = SourceResolver(provider_priorities={"provider-a": 7})

        episode_playback = resolver.resolve(anime, season, episode)

        assert episode_playback.sources[0].provider.priority == 7


class TestSelectBest:
    def test_returns_best_available_source(self) -> None:
        anime, season, episode = make_anime_season_episode(
            [
                make_streaming_source(provider_name="provider-a", quality=StreamQuality.SD),
                make_streaming_source(provider_name="provider-b", quality=StreamQuality.UHD),
            ]
        )
        resolver = SourceResolver()
        episode_playback = resolver.resolve(anime, season, episode)

        best = resolver.select_best(episode_playback)

        assert best.quality == StreamQuality.UHD

    def test_raises_when_no_sources(self) -> None:
        anime, season, episode = make_anime_season_episode([])
        resolver = SourceResolver()
        episode_playback = resolver.resolve(anime, season, episode)

        with pytest.raises(NoAvailableSourceError):
            resolver.select_best(episode_playback)


class TestSelectByQuality:
    def test_returns_matching_quality_source(self) -> None:
        anime, season, episode = make_anime_season_episode(
            [
                make_streaming_source(provider_name="provider-a", quality=StreamQuality.SD),
                make_streaming_source(provider_name="provider-b", quality=StreamQuality.HD),
            ]
        )
        resolver = SourceResolver()
        episode_playback = resolver.resolve(anime, season, episode)

        selected = resolver.select_by_quality(episode_playback, StreamQuality.HD)

        assert selected.quality == StreamQuality.HD
