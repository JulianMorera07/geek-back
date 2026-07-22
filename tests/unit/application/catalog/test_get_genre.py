import pytest

from geekbaku.application.catalog.dto import CreateGenreCommand
from geekbaku.application.catalog.use_cases.create_genre import CreateGenre
from geekbaku.application.catalog.use_cases.get_genre import GetGenre
from geekbaku.domain.catalog.exceptions import GenreNotFoundError
from geekbaku.domain.catalog.value_objects import GenreId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_returns_genre_by_id() -> None:
    uow = FakeCatalogUnitOfWork()
    created = await CreateGenre(uow).execute(CreateGenreCommand(name="Shonen", slug="shonen"))

    result = await GetGenre(uow).execute(created.id)

    assert result.slug == "shonen"


async def test_raises_when_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(GenreNotFoundError):
        await GetGenre(uow).execute(str(GenreId.new()))
