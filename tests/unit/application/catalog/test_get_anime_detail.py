import pytest

from geekbaku.application.catalog.dto import CreateAnimeCommand
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.application.catalog.use_cases.get_anime_detail import GetAnimeDetail
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_returns_detail_for_existing_slug() -> None:
    uow = FakeCatalogUnitOfWork()
    await CreateAnime(uow).execute(
        CreateAnimeCommand(
            title="Attack on Titan", slug="attack-on-titan", type="tv", status="ongoing"
        )
    )

    detail = await GetAnimeDetail(uow).execute("attack-on-titan")

    assert detail.slug == "attack-on-titan"
    assert detail.title == "Attack on Titan"


async def test_raises_when_slug_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(AnimeNotFoundError):
        await GetAnimeDetail(uow).execute("does-not-exist")
