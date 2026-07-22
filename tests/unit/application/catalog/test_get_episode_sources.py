import pytest

from geekbaku.application.catalog.use_cases.get_episode_sources import GetEpisodeSources
from geekbaku.domain.catalog.entities import Episode, StreamingSource
from geekbaku.domain.catalog.exceptions import EpisodeNotFoundError
from geekbaku.domain.catalog.value_objects import (
    EpisodeId,
    EpisodeNumber,
    Language,
    StreamingSourceId,
    StreamQuality,
    Title,
)
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio

JAPANESE = Language(code="ja", name="Japanese")


def _source(quality: StreamQuality, ref: str, is_active: bool = True) -> StreamingSource:
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


async def test_returns_active_sources_ordered_by_quality() -> None:
    uow = FakeCatalogUnitOfWork()
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    episode.add_streaming_source(_source(StreamQuality.SD, "sd"))
    episode.add_streaming_source(_source(StreamQuality.UHD, "uhd"))
    episode.add_streaming_source(_source(StreamQuality.FHD, "fhd", is_active=False))
    uow.register_episode(episode)

    sources = await GetEpisodeSources(uow).execute(str(episode.id))

    assert [s.quality for s in sources] == ["uhd", "sd"]


async def test_returns_empty_tuple_when_no_active_sources() -> None:
    uow = FakeCatalogUnitOfWork()
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    uow.register_episode(episode)

    sources = await GetEpisodeSources(uow).execute(str(episode.id))

    assert sources == ()


async def test_raises_when_episode_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(EpisodeNotFoundError):
        await GetEpisodeSources(uow).execute(str(EpisodeId.new()))
