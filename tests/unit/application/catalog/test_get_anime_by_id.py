import pytest

from geekbaku.application.catalog.dto import CreateAnimeCommand
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.application.catalog.use_cases.get_anime_by_id import GetAnimeById
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import AnimeId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_returns_detail_for_existing_id() -> None:
    uow = FakeCatalogUnitOfWork()
    created = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )

    detail = await GetAnimeById(uow).execute(created.id)

    assert detail.id == created.id
    assert detail.title == "Frieren"


async def test_raises_when_id_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(AnimeNotFoundError):
        await GetAnimeById(uow).execute(str(AnimeId.new()))
