from datetime import UTC, datetime, timedelta

import pytest

from geekbaku.domain.catalog.value_objects import EpisodeId, Language, StreamQuality, VideoUrl
from geekbaku.domain.playback.entities import EpisodePlayback, PlaybackSession, PlaybackSource
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
    WatchProgress,
)

JAPANESE = Language(code="ja", name="Japanese")


def make_source(
    quality: StreamQuality = StreamQuality.HD,
    is_active: bool = True,
    expires_at: datetime | None = None,
) -> PlaybackSource:
    return PlaybackSource(
        id=PlaybackSourceId.new(),
        provider=PlaybackProvider(provider_id="provider-a"),
        streaming_server=StreamingServer(name="provider-a", base_url="https://cdn.example.com"),
        url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
        quality=quality,
        audio_track=AudioTrack(language=JAPANESE),
        is_active=is_active,
        expires_at=expires_at,
    )


def make_metadata() -> PlaybackMetadata:
    return PlaybackMetadata(
        title="Episode 1", anime_title="Attack on Titan", season_number=1, episode_number=1
    )


class TestPlaybackSource:
    def test_is_available_when_active_and_not_expired(self) -> None:
        source = make_source()
        assert source.is_available() is True

    def test_is_not_available_when_inactive(self) -> None:
        source = make_source(is_active=False)
        assert source.is_available() is False

    def test_is_expired_when_expires_at_passed(self) -> None:
        past = datetime.now(UTC) - timedelta(hours=1)
        source = make_source(expires_at=past)
        assert source.is_expired() is True
        assert source.is_available() is False

    def test_not_expired_without_expires_at(self) -> None:
        source = make_source()
        assert source.is_expired() is False

    def test_deactivate(self) -> None:
        source = make_source()
        source.deactivate()
        assert source.is_active is False

    def test_equality_by_id(self) -> None:
        source_id = PlaybackSourceId.new()
        a = PlaybackSource(
            id=source_id,
            provider=PlaybackProvider(provider_id="provider-a"),
            streaming_server=StreamingServer(name="a", base_url="https://x.com"),
            url=VideoUrl("https://x.com/a.m3u8"),
            quality=StreamQuality.HD,
            audio_track=AudioTrack(language=JAPANESE),
        )
        b = PlaybackSource(
            id=source_id,
            provider=PlaybackProvider(provider_id="provider-b"),
            streaming_server=StreamingServer(name="b", base_url="https://y.com"),
            url=VideoUrl("https://y.com/b.m3u8"),
            quality=StreamQuality.SD,
            audio_track=AudioTrack(language=JAPANESE),
        )
        assert a == b
        assert hash(a) == hash(b)


class TestEpisodePlayback:
    def test_available_sources_excludes_inactive(self) -> None:
        episode_playback = EpisodePlayback(episode_id=EpisodeId.new(), metadata=make_metadata())
        active = make_source()
        inactive = make_source(is_active=False)
        episode_playback.add_source(active)
        episode_playback.add_source(inactive)

        assert episode_playback.available_sources == (active,)
        assert episode_playback.sources == (active, inactive)

    def test_get_source_returns_matching_source(self) -> None:
        episode_playback = EpisodePlayback(episode_id=EpisodeId.new(), metadata=make_metadata())
        source = make_source()
        episode_playback.add_source(source)

        assert episode_playback.get_source(source.id) is source

    def test_get_source_raises_when_not_found(self) -> None:
        episode_playback = EpisodePlayback(episode_id=EpisodeId.new(), metadata=make_metadata())
        with pytest.raises(SourceNotFoundError):
            episode_playback.get_source(PlaybackSourceId.new())

    def test_available_qualities_deduplicates(self) -> None:
        episode_playback = EpisodePlayback(episode_id=EpisodeId.new(), metadata=make_metadata())
        episode_playback.add_source(make_source(quality=StreamQuality.HD))
        episode_playback.add_source(make_source(quality=StreamQuality.HD))
        episode_playback.add_source(make_source(quality=StreamQuality.SD))

        assert set(episode_playback.available_qualities()) == {StreamQuality.HD, StreamQuality.SD}


class TestPlaybackSession:
    def test_defaults_to_active(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        assert session.status == PlaybackSessionStatus.ACTIVE

    def test_select_source_updates_selection(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        source_id = PlaybackSourceId.new()
        session.select_source(source_id)
        assert session.selected_source_id == source_id

    def test_select_quality_updates_selection(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        session.select_quality(StreamQuality.FHD)
        assert session.selected_quality == StreamQuality.FHD

    def test_select_subtitle_none_means_explicitly_no_subtitles(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        session.select_subtitle(JAPANESE)
        session.select_subtitle(None)
        assert session.selected_subtitle_language is None

    def test_update_progress(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        progress = WatchProgress.at(10, 100)
        session.update_progress(progress)
        assert session.progress == progress

    def test_pause_and_resume(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        session.pause()
        status_after_pause = session.status
        assert status_after_pause == PlaybackSessionStatus.PAUSED
        session.resume()
        status_after_resume = session.status
        assert status_after_resume == PlaybackSessionStatus.ACTIVE

    def test_complete_is_terminal(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        session.complete()
        with pytest.raises(InvalidSessionTransitionError):
            session.resume()

    def test_abandon_can_be_resumed(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        session.abandon()
        session.resume()
        assert session.status == PlaybackSessionStatus.ACTIVE

    def test_same_status_transition_is_noop(self) -> None:
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        updated_at_before = session.updated_at
        session.resume()  # ya está ACTIVE
        assert session.updated_at == updated_at_before

    def test_equality_by_id(self) -> None:
        session_id = PlaybackSessionId.new()
        a = PlaybackSession(id=session_id, episode_id=EpisodeId.new())
        b = PlaybackSession(id=session_id, episode_id=EpisodeId.new())
        assert a == b
        assert hash(a) == hash(b)
