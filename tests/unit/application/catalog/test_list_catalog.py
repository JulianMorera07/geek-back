import pytest

from geekbaku.application.catalog.dto import CreateAnimeCommand, ListCatalogQuery
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.application.catalog.use_cases.list_catalog import ListCatalog
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def _seed(uow: FakeCatalogUnitOfWork) -> None:
    create = CreateAnime(uow)
    await create.execute(
        CreateAnimeCommand(
            title="Attack on Titan", slug="attack-on-titan", type="tv", status="ongoing"
        )
    )
    await create.execute(
        CreateAnimeCommand(title="Your Name", slug="your-name", type="movie", status="completed")
    )
    await create.execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )


async def test_lists_all_when_no_filters() -> None:
    uow = FakeCatalogUnitOfWork()
    await _seed(uow)

    page = await ListCatalog(uow).execute(ListCatalogQuery())

    assert page.total == 3
    assert len(page.items) == 3


async def test_filters_by_status_and_type() -> None:
    uow = FakeCatalogUnitOfWork()
    await _seed(uow)

    page = await ListCatalog(uow).execute(ListCatalogQuery(status="ongoing", type="tv"))

    assert page.total == 2
    assert {item.slug for item in page.items} == {"attack-on-titan", "frieren"}


async def test_paginates_results() -> None:
    uow = FakeCatalogUnitOfWork()
    await _seed(uow)

    page = await ListCatalog(uow).execute(ListCatalogQuery(page=1, page_size=2))

    assert page.total == 3
    assert len(page.items) == 2
    assert page.page == 1
    assert page.page_size == 2
