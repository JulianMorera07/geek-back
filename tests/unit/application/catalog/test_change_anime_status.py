import pytest

from geekbaku.application.catalog.dto import ChangeAnimeStatusCommand, CreateAnimeCommand
from geekbaku.application.catalog.use_cases.change_anime_status import ChangeAnimeStatus
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError, InvalidStatusTransitionError
from geekbaku.domain.catalog.value_objects import AnimeId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_applies_valid_transition() -> None:
    uow = FakeCatalogUnitOfWork()
    created = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="announced")
    )

    updated = await ChangeAnimeStatus(uow).execute(
        ChangeAnimeStatusCommand(anime_id=created.id, new_status="ongoing")
    )

    assert updated.status == "ongoing"


async def test_rejects_invalid_transition() -> None:
    uow = FakeCatalogUnitOfWork()
    created = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="completed")
    )

    with pytest.raises(InvalidStatusTransitionError):
        await ChangeAnimeStatus(uow).execute(
            ChangeAnimeStatusCommand(anime_id=created.id, new_status="ongoing")
        )


async def test_raises_when_anime_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(AnimeNotFoundError):
        await ChangeAnimeStatus(uow).execute(
            ChangeAnimeStatusCommand(anime_id=str(AnimeId.new()), new_status="ongoing")
        )
