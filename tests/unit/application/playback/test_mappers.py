import pytest

from geekbaku.application.playback.mappers import (
    parse_playback_session_id,
    parse_playback_source_id,
    parse_subtitle_language,
    to_playback_metadata,
    to_playback_source,
)
from geekbaku.domain.catalog.entities import Anime, Episode, Season, StreamingSource
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeType,
    Duration,
    EpisodeId,
    EpisodeNumber,
    Language,
    Media,
    MediaKind,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    Title,
    VideoUrl,
)
from geekbaku.domain.shared.errors import ValidationError

JAPANESE = Language(code="ja", name="Japanese")


class TestParsePlaybackSessionId:
    def test_rejects_invalid_uuid(self) -> None:
        with pytest.raises(ValidationError):
            parse_playback_session_id("not-a-uuid")


class TestParsePlaybackSourceId:
    def test_rejects_invalid_uuid(self) -> None:
        with pytest.raises(ValidationError):
            parse_playback_source_id("not-a-uuid")


class TestParseSubtitleLanguage:
    def test_returns_none_without_code_or_name(self) -> None:
        assert parse_subtitle_language(None, None) is None

    def test_returns_language_with_both(self) -> None:
        language = parse_subtitle_language("en", "English")
        assert language is not None
        assert language.code == "en"


class TestToPlaybackSource:
    def test_returns_none_when_url_missing(self) -> None:
        streaming_source = StreamingSource(
            id=StreamingSourceId.new(),
            provider_name="provider-a",
            external_ref="ep-1",
            quality=StreamQuality.HD,
            audio_language=JAPANESE,
        )
        assert to_playback_source(streaming_source) is None

    def test_maps_active_source_with_url(self) -> None:
        streaming_source = StreamingSource(
            id=StreamingSourceId.new(),
            provider_name="provider-a",
            external_ref="ep-1",
            quality=StreamQuality.HD,
            audio_language=JAPANESE,
            url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
        )

        source = to_playback_source(streaming_source, provider_priority=5)

        assert source is not None
        assert source.id.value == streaming_source.id.value
        assert source.provider.provider_id == "provider-a"
        assert source.provider.priority == 5
        assert source.streaming_server.base_url == "https://cdn.example.com"
        assert source.quality == StreamQuality.HD

    def test_maps_subtitle_language_as_hardsub(self) -> None:
        streaming_source = StreamingSource(
            id=StreamingSourceId.new(),
            provider_name="provider-a",
            external_ref="ep-1",
            quality=StreamQuality.HD,
            audio_language=JAPANESE,
            subtitle_language=Language(code="en", name="English"),
            url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
        )

        source = to_playback_source(streaming_source)

        assert source is not None
        assert len(source.subtitles) == 1
        assert source.subtitles[0].url is None
        assert source.subtitles[0].language.code == "en"

    def test_inactive_source_maps_but_stays_inactive(self) -> None:
        streaming_source = StreamingSource(
            id=StreamingSourceId.new(),
            provider_name="provider-a",
            external_ref="ep-1",
            quality=StreamQuality.HD,
            audio_language=JAPANESE,
            url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
            is_active=False,
        )

        source = to_playback_source(streaming_source)

        assert source is not None
        assert source.is_active is False


class TestToPlaybackMetadata:
    def test_maps_all_fields(self) -> None:
        anime = Anime(
            id=AnimeId.new(),
            title=Title("Attack on Titan"),
            slug=Slug("attack-on-titan"),
            anime_type=AnimeType.TV,
        )
        season = Season(id=SeasonId.new(), number=SeasonNumber(1))
        episode = Episode(
            id=EpisodeId.new(),
            number=EpisodeNumber(1),
            title=Title("To You, in 2000 Years"),
            duration=Duration(24),
        )
        episode.add_media(Media(kind=MediaKind.THUMBNAIL, url="https://cdn.example.com/t.jpg"))

        metadata = to_playback_metadata(anime, season, episode)

        assert metadata.title == "To You, in 2000 Years"
        assert metadata.anime_title == "Attack on Titan"
        assert metadata.season_number == 1
        assert metadata.episode_number == 1
        assert metadata.duration_seconds == 24 * 60
        assert metadata.thumbnail_url == "https://cdn.example.com/t.jpg"

    def test_handles_missing_duration_and_thumbnail(self) -> None:
        anime = Anime(
            id=AnimeId.new(), title=Title("X"), slug=Slug("x"), anime_type=AnimeType.TV
        )
        season = Season(id=SeasonId.new(), number=SeasonNumber(1))
        episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Ep 1"))

        metadata = to_playback_metadata(anime, season, episode)

        assert metadata.duration_seconds is None
        assert metadata.thumbnail_url is None
