import pytest

from geekbaku.application.catalog.dto import AddEpisodeCommand, AddSeasonCommand, CreateAnimeCommand
from geekbaku.application.catalog.use_cases.add_episode import AddEpisode
from geekbaku.application.catalog.use_cases.add_season import AddSeason
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.application.catalog.use_cases.get_anime_episodes import GetAnimeEpisodes
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import AnimeId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_flattens_episodes_ordered_by_season_and_number() -> None:
    uow = FakeCatalogUnitOfWork()
    anime = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )
    season_two = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime.id, number=2))
    season_one = await AddSeason(uow).execute(AddSeasonCommand(anime_id=anime.id, number=1))

    await AddEpisode(uow).execute(
        AddEpisodeCommand(anime_id=anime.id, season_id=season_two.id, number=1, title="S2E1")
    )
    await AddEpisode(uow).execute(
        AddEpisodeCommand(anime_id=anime.id, season_id=season_one.id, number=2, title="S1E2")
    )
    await AddEpisode(uow).execute(
        AddEpisodeCommand(anime_id=anime.id, season_id=season_one.id, number=1, title="S1E1")
    )

    episodes = await GetAnimeEpisodes(uow).execute(anime.id)

    assert [e.title for e in episodes] == ["S1E1", "S1E2", "S2E1"]


async def test_raises_when_anime_not_found() -> None:
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(AnimeNotFoundError):
        await GetAnimeEpisodes(uow).execute(str(AnimeId.new()))


async def test_returns_empty_tuple_when_no_episodes() -> None:
    uow = FakeCatalogUnitOfWork()
    anime = await CreateAnime(uow).execute(
        CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
    )

    episodes = await GetAnimeEpisodes(uow).execute(anime.id)

    assert episodes == ()
