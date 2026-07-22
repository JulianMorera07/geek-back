import pytest

from geekbaku.application.catalog.dto import (
    AddAnimeExternalIdCommand,
    AddEpisodeCommand,
    AddEpisodeExternalIdCommand,
    AddSeasonCommand,
    CreateAnimeCommand,
)
from geekbaku.application.catalog.use_cases.add_anime_external_id import AddAnimeExternalId
from geekbaku.application.catalog.use_cases.add_episode import AddEpisode
from geekbaku.application.catalog.use_cases.add_episode_external_id import AddEpisodeExternalId
from geekbaku.application.catalog.use_cases.add_season import AddSeason
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.domain.catalog.exceptions import DuplicateExternalIdError
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def _create_anime_with_episode(uow: FakeCatalogUnitOfWork) -> tuple[str, str]:
    anime = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )
    season = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime.id, number=1))
    episode = await AddEpisode(uow).execute(
        AddEpisodeCommand(anime_id=anime.id, season_id=season.id, number=1, title="Episode 1")
    )
    return anime.id, episode.id


class TestAddAnimeExternalId:
    async def test_adds_external_id(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, _ = await _create_anime_with_episode(uow)

        result = await AddAnimeExternalId(uow).execute(
            AddAnimeExternalIdCommand(anime_id=anime_id, source="mal", value="12345")
        )

        assert result.source == "mal"
        assert result.value == "12345"

    async def test_rejects_duplicate_source(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, _ = await _create_anime_with_episode(uow)
        command = AddAnimeExternalIdCommand(anime_id=anime_id, source="mal", value="12345")
        await AddAnimeExternalId(uow).execute(command)

        with pytest.raises(DuplicateExternalIdError):
            await AddAnimeExternalId(uow).execute(command)


class TestAddEpisodeExternalId:
    async def test_adds_external_id(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, episode_id = await _create_anime_with_episode(uow)

        result = await AddEpisodeExternalId(uow).execute(
            AddEpisodeExternalIdCommand(
                anime_id=anime_id, episode_id=episode_id, source="tvdb", value="ep-1"
            )
        )

        assert result.source == "tvdb"

    async def test_rejects_duplicate_source(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, episode_id = await _create_anime_with_episode(uow)
        command = AddEpisodeExternalIdCommand(
            anime_id=anime_id, episode_id=episode_id, source="tvdb", value="ep-1"
        )
        await AddEpisodeExternalId(uow).execute(command)

        with pytest.raises(DuplicateExternalIdError):
            await AddEpisodeExternalId(uow).execute(command)
