import pytest

from geekbaku.application.catalog.dto import AddEpisodeCommand, AddSeasonCommand, CreateAnimeCommand
from geekbaku.application.catalog.use_cases.add_episode import AddEpisode
from geekbaku.application.catalog.use_cases.add_season import AddSeason
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.domain.catalog.exceptions import (
    AnimeNotFoundError,
    DuplicateEpisodeNumberError,
    DuplicateSeasonNumberError,
    SeasonNotFoundError,
)
from geekbaku.domain.catalog.value_objects import AnimeId, SeasonId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def _create_anime(uow: FakeCatalogUnitOfWork) -> str:
    result = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )
    return result.id


class TestAddSeason:
    async def test_adds_season(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id = await _create_anime(uow)

        season = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime_id, number=1))

        assert season.number == 1

    async def test_rejects_duplicate_number(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id = await _create_anime(uow)
        await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime_id, number=1))

        with pytest.raises(DuplicateSeasonNumberError):
            await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime_id, number=1))

    async def test_raises_when_anime_not_found(self) -> None:
        uow = FakeCatalogUnitOfWork()

        with pytest.raises(AnimeNotFoundError):
            await AddSeason(uow).execute(
                AddSeasonCommand(anime_id=str(AnimeId.new()), number=1)
            )


class TestAddEpisode:
    async def test_adds_episode(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id = await _create_anime(uow)
        season = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime_id, number=1))

        episode = await AddEpisode(uow).execute(
            AddEpisodeCommand(
                anime_id=anime_id,
                season_id=season.id,
                number=1,
                title="The Journey's End",
                duration_minutes=24,
            )
        )

        assert episode.number == 1
        assert episode.duration_minutes == 24

    async def test_rejects_duplicate_number(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id = await _create_anime(uow)
        season = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime_id, number=1))
        command = AddEpisodeCommand(
            anime_id=anime_id, season_id=season.id, number=1, title="Episode 1"
        )
        await AddEpisode(uow).execute(command)

        with pytest.raises(DuplicateEpisodeNumberError):
            await AddEpisode(uow).execute(command)

    async def test_raises_when_season_not_found(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id = await _create_anime(uow)

        with pytest.raises(SeasonNotFoundError):
            await AddEpisode(uow).execute(
                AddEpisodeCommand(
                    anime_id=anime_id,
                    season_id=str(SeasonId.new()),
                    number=1,
                    title="Episode 1",
                )
            )
