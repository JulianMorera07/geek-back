from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Season
from geekbaku.domain.catalog.value_objects import (
    AnimeFilter,
    AnimeId,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    GenreId,
    SeasonId,
    SeasonNumber,
    Slug,
    Title,
)
from geekbaku.infrastructure.catalog.repositories.in_memory_catalog_repository import (
    InMemoryCatalogUnitOfWork,
)


def make_anime_with_episode() -> tuple[Anime, Episode]:
    anime = Anime(
        id=AnimeId.new(),
        title=Title("Example Anime"),
        slug=Slug("example-anime"),
        anime_type=AnimeType.TV,
    )
    season = Season(id=SeasonId.new(), number=SeasonNumber(1))
    episode = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    season.add_episode(episode)
    anime.add_season(season)
    return anime, episode


class TestInMemoryCatalogUnitOfWork:
    async def test_is_usable_as_an_async_context_manager(self) -> None:
        async with InMemoryCatalogUnitOfWork() as uow:
            await uow.commit()

        assert uow.committed is True

    async def test_starts_empty(self) -> None:
        uow = InMemoryCatalogUnitOfWork()

        results, total = await uow.animes.list(AnimeFilter(), Pagination())

        assert results == []
        assert total == 0


class TestEpisodeRepositorySharesAnimeState:
    async def test_finds_episode_belonging_to_a_persisted_anime(self) -> None:
        uow = InMemoryCatalogUnitOfWork()
        anime, episode = make_anime_with_episode()
        await uow.animes.add(anime)

        found = await uow.episodes.get_by_id(episode.id)

        assert found is episode

    async def test_returns_none_for_unknown_episode(self) -> None:
        uow = InMemoryCatalogUnitOfWork()

        found = await uow.episodes.get_by_id(EpisodeId.new())

        assert found is None

    async def test_does_not_require_manual_registration(self) -> None:
        """A diferencia de `FakeCatalogUnitOfWork` (test double), acá no
        hace falta un paso extra `register_episode`: agregar el `Anime`
        alcanza para que `EpisodeRepository` encuentre sus episodios."""
        uow = InMemoryCatalogUnitOfWork()
        anime, episode = make_anime_with_episode()

        await uow.animes.add(anime)

        assert not hasattr(uow, "register_episode")
        assert await uow.episodes.get_by_id(episode.id) is episode


class TestGenreRepository:
    async def test_add_and_get_by_slug(self) -> None:
        uow = InMemoryCatalogUnitOfWork()
        genre = Genre(id=GenreId.new(), name="Action", slug=Slug("action"))

        await uow.genres.add(genre)

        assert await uow.genres.get_by_slug(Slug("action")) is genre
        assert await uow.genres.get_by_slug(Slug("unknown")) is None
