from geekbaku.domain.catalog.entities import Anime, Episode, StreamingSource
from geekbaku.domain.catalog.services import EpisodeAvailabilityService, RelationLinkingService
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    Language,
    RelationType,
    Slug,
    StreamingSourceId,
    StreamQuality,
    Title,
)

JAPANESE = Language(code="ja", name="Japanese")


def make_anime(title: str) -> Anime:
    return Anime(
        id=AnimeId.new(),
        title=Title(title),
        slug=Slug(title.lower().replace(" ", "-")),
        anime_type=AnimeType.TV,
    )


def make_episode() -> Episode:
    return Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))


def make_source(
    quality: StreamQuality, is_active: bool = True, ref: str = "ep-1"
) -> StreamingSource:
    source = StreamingSource(
        id=StreamingSourceId.new(),
        provider_name="provider_a",
        external_ref=ref,
        quality=quality,
        audio_language=JAPANESE,
        is_active=is_active,
    )
    if not is_active:
        source.deactivate()
    return source


class TestRelationLinkingService:
    def test_link_adds_relation_and_inverse(self) -> None:
        source = make_anime("Attack on Titan")
        target = make_anime("Attack on Titan Season 2")

        RelationLinkingService.link(source, target, RelationType.SEQUEL)

        assert source.relations[0].related_anime_id == target.id
        assert source.relations[0].relation_type == RelationType.SEQUEL
        assert target.relations[0].related_anime_id == source.id
        assert target.relations[0].relation_type == RelationType.PREQUEL


class TestEpisodeAvailabilityService:
    def test_is_available_false_without_sources(self) -> None:
        episode = make_episode()
        assert EpisodeAvailabilityService.is_available(episode) is False

    def test_is_available_false_when_all_inactive(self) -> None:
        episode = make_episode()
        episode.add_streaming_source(make_source(StreamQuality.HD, is_active=False))
        assert EpisodeAvailabilityService.is_available(episode) is False

    def test_is_available_true_with_active_source(self) -> None:
        episode = make_episode()
        episode.add_streaming_source(make_source(StreamQuality.HD))
        assert EpisodeAvailabilityService.is_available(episode) is True

    def test_best_source_returns_none_without_active_sources(self) -> None:
        episode = make_episode()
        assert EpisodeAvailabilityService.best_source(episode) is None

    def test_best_source_picks_highest_quality(self) -> None:
        episode = make_episode()
        sd_source = make_source(StreamQuality.SD, ref="sd")
        uhd_source = make_source(StreamQuality.UHD, ref="uhd")
        episode.add_streaming_source(sd_source)
        episode.add_streaming_source(uhd_source)

        best = EpisodeAvailabilityService.best_source(episode)

        assert best is uhd_source

    def test_best_source_ignores_inactive_sources(self) -> None:
        episode = make_episode()
        uhd_inactive = make_source(StreamQuality.UHD, is_active=False, ref="uhd")
        hd_active = make_source(StreamQuality.HD, ref="hd")
        episode.add_streaming_source(uhd_inactive)
        episode.add_streaming_source(hd_active)

        best = EpisodeAvailabilityService.best_source(episode)

        assert best is hd_active
