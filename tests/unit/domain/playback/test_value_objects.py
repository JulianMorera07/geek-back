from datetime import UTC, datetime

import pytest

from geekbaku.domain.catalog.value_objects import Language
from geekbaku.domain.playback.value_objects import (
    PlaybackMetadata,
    PlaybackProvider,
    ResumePoint,
    StreamingServer,
    Subtitle,
    SubtitleFormat,
    SubtitleUrl,
    WatchProgress,
)
from geekbaku.domain.shared.errors import ValidationError

JAPANESE = Language(code="ja", name="Japanese")


class TestSubtitleUrl:
    def test_accepts_http_url(self) -> None:
        assert SubtitleUrl("https://cdn.example.com/subs.vtt").value.endswith(".vtt")

    def test_rejects_invalid_url(self) -> None:
        with pytest.raises(ValidationError):
            SubtitleUrl("not-a-url")


class TestSubtitle:
    def test_url_is_optional_for_hardsub(self) -> None:
        subtitle = Subtitle(language=JAPANESE, format=SubtitleFormat.VTT, url=None)
        assert subtitle.url is None

    def test_accepts_softsub_url(self) -> None:
        subtitle = Subtitle(
            language=JAPANESE,
            format=SubtitleFormat.VTT,
            url=SubtitleUrl("https://cdn.example.com/subs.vtt"),
        )
        assert subtitle.url is not None


class TestStreamingServer:
    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            StreamingServer(name=" ", base_url="https://cdn.example.com")

    def test_rejects_invalid_base_url(self) -> None:
        with pytest.raises(ValidationError):
            StreamingServer(name="server1", base_url="not-a-url")


class TestPlaybackProvider:
    def test_rejects_empty_provider_id(self) -> None:
        with pytest.raises(ValidationError):
            PlaybackProvider(provider_id=" ")

    def test_defaults_priority_to_zero(self) -> None:
        assert PlaybackProvider(provider_id="jikan").priority == 0


class TestPlaybackMetadata:
    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValidationError):
            PlaybackMetadata(title=" ", anime_title="X", season_number=1, episode_number=1)

    def test_rejects_non_positive_season_number(self) -> None:
        with pytest.raises(ValidationError):
            PlaybackMetadata(title="Ep 1", anime_title="X", season_number=0, episode_number=1)

    def test_rejects_non_positive_episode_number(self) -> None:
        with pytest.raises(ValidationError):
            PlaybackMetadata(title="Ep 1", anime_title="X", season_number=1, episode_number=0)

    def test_rejects_non_positive_duration(self) -> None:
        with pytest.raises(ValidationError):
            PlaybackMetadata(
                title="Ep 1",
                anime_title="X",
                season_number=1,
                episode_number=1,
                duration_seconds=0,
            )

    def test_accepts_minimal_metadata(self) -> None:
        metadata = PlaybackMetadata(
            title="Ep 1", anime_title="X", season_number=1, episode_number=1
        )
        assert metadata.duration_seconds is None


class TestWatchProgress:
    def test_rejects_negative_position(self) -> None:
        with pytest.raises(ValidationError):
            WatchProgress(position_seconds=-1, duration_seconds=100, updated_at=datetime.now(UTC))

    def test_rejects_non_positive_duration(self) -> None:
        with pytest.raises(ValidationError):
            WatchProgress(position_seconds=0, duration_seconds=0, updated_at=datetime.now(UTC))

    def test_rejects_position_past_duration(self) -> None:
        with pytest.raises(ValidationError):
            WatchProgress(position_seconds=101, duration_seconds=100, updated_at=datetime.now(UTC))

    def test_percentage(self) -> None:
        progress = WatchProgress(
            position_seconds=25, duration_seconds=100, updated_at=datetime.now(UTC)
        )
        assert progress.percentage == 25.0

    def test_at_factory_sets_updated_at(self) -> None:
        progress = WatchProgress.at(10, 100)
        assert progress.position_seconds == 10
        assert progress.updated_at is not None


class TestResumePoint:
    def test_rejects_negative_position(self) -> None:
        with pytest.raises(ValidationError):
            ResumePoint(position_seconds=-1, is_completed=False)
