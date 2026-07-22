import pytest

from geekbaku.application.catalog.use_cases.get_episode_by_id import GetEpisodeById
from geekbaku.domain.catalog.entities import Episode
from geekbaku.domain.catalog.exceptions import EpisodeNotFoundError
from geekbaku.domain.catalog.value_objects import EpisodeId, EpisodeNumber, Title
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_returns_episode_dto() -> None:
    uow = FakeCatalogUnitOfWork()
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    uow.register_episode(episode)

    result = await GetEpisodeById(uow).execute(str(episode.id))

    assert result.id == str(episode.id)
    assert result.title == "Episode 1"


async def test_raises_when_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(EpisodeNotFoundError):
        await GetEpisodeById(uow).execute(str(EpisodeId.new()))
