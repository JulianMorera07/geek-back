import pytest

from geekbaku.domain.catalog.value_objects import Language, StreamQuality, VideoUrl
from geekbaku.domain.playback.entities import PlaybackSource
from geekbaku.domain.playback.exceptions import NoAvailableSourceError, QualityNotAvailableError
from geekbaku.domain.playback.services import ResumePointService, SourceSelectionService
from geekbaku.domain.playback.value_objects import (
    AudioTrack,
    PlaybackProvider,
    PlaybackSourceId,
    StreamingServer,
    WatchProgress,
)

JAPANESE = Language(code="ja", name="Japanese")


def make_source(
    provider_id: str = "provider-a",
    priority: int = 0,
    quality: StreamQuality = StreamQuality.HD,
    is_active: bool = True,
) -> PlaybackSource:
    source = PlaybackSource(
        id=PlaybackSourceId.new(),
        provider=PlaybackProvider(provider_id=provider_id, priority=priority),
        streaming_server=StreamingServer(name=provider_id, base_url="https://cdn.example.com"),
        url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
        quality=quality,
        audio_track=AudioTrack(language=JAPANESE),
    )
    if not is_active:
        source.deactivate()
    return source


class TestSourceSelectionServiceRank:
    def test_excludes_unavailable_sources(self) -> None:
        active = make_source()
        inactive = make_source(is_active=False)
        ranked = SourceSelectionService.rank([active, inactive])
        assert ranked == [active]

    def test_prefers_matching_preferred_quality(self) -> None:
        sd = make_source(quality=StreamQuality.SD)
        hd = make_source(quality=StreamQuality.HD)
        ranked = SourceSelectionService.rank([sd, hd], preferred_quality=StreamQuality.SD)
        assert ranked[0] is sd

    def test_falls_back_to_best_quality_when_preferred_unavailable(self) -> None:
        sd = make_source(quality=StreamQuality.SD)
        uhd = make_source(quality=StreamQuality.UHD)
        ranked = SourceSelectionService.rank([sd, uhd], preferred_quality=StreamQuality.FHD)
        # ninguna coincide exactamente con FHD: cae al orden por mejor calidad
        assert ranked[0] is uhd

    def test_orders_by_explicit_provider_priority_list(self) -> None:
        a = make_source(provider_id="provider-a")
        b = make_source(provider_id="provider-b")
        ranked = SourceSelectionService.rank(
            [a, b], preferred_provider_ids=("provider-b", "provider-a")
        )
        assert ranked[0] is b

    def test_orders_by_provider_own_priority_when_no_explicit_list(self) -> None:
        low = make_source(provider_id="provider-low", priority=1)
        high = make_source(provider_id="provider-high", priority=10)
        ranked = SourceSelectionService.rank([low, high])
        assert ranked[0] is high

    def test_empty_input_yields_empty_ranking(self) -> None:
        assert SourceSelectionService.rank([]) == []


class TestSourceSelectionServiceSelectBest:
    def test_returns_top_ranked_source(self) -> None:
        low = make_source(provider_id="provider-low", priority=1)
        high = make_source(provider_id="provider-high", priority=10)
        assert SourceSelectionService.select_best([low, high]) is high

    def test_raises_when_no_sources_available(self) -> None:
        with pytest.raises(NoAvailableSourceError):
            SourceSelectionService.select_best([])

    def test_raises_when_all_sources_inactive(self) -> None:
        with pytest.raises(NoAvailableSourceError):
            SourceSelectionService.select_best([make_source(is_active=False)])


class TestSourceSelectionServiceSelectByQuality:
    def test_returns_matching_quality(self) -> None:
        sd = make_source(quality=StreamQuality.SD)
        hd = make_source(quality=StreamQuality.HD)
        assert SourceSelectionService.select_by_quality([sd, hd], StreamQuality.HD) is hd

    def test_raises_when_quality_not_available(self) -> None:
        with pytest.raises(QualityNotAvailableError):
            SourceSelectionService.select_by_quality(
                [make_source(quality=StreamQuality.SD)], StreamQuality.UHD
            )


class TestResumePointService:
    def test_no_progress_starts_from_zero(self) -> None:
        resume_point = ResumePointService.compute(None)
        assert resume_point.position_seconds == 0
        assert resume_point.is_completed is False

    def test_near_complete_progress_restarts_and_marks_completed(self) -> None:
        progress = WatchProgress.at(96, 100)
        resume_point = ResumePointService.compute(progress)
        assert resume_point.position_seconds == 0
        assert resume_point.is_completed is True

    def test_insignificant_progress_restarts_without_marking_completed(self) -> None:
        progress = WatchProgress.at(1, 100)
        resume_point = ResumePointService.compute(progress)
        assert resume_point.position_seconds == 0
        assert resume_point.is_completed is False

    def test_meaningful_progress_resumes_at_saved_position(self) -> None:
        progress = WatchProgress.at(50, 100)
        resume_point = ResumePointService.compute(progress)
        assert resume_point.position_seconds == 50
        assert resume_point.is_completed is False
