import pytest

from geekbaku.application.catalog.dto import (
    CreateGenreCommand,
    CreateProducerCommand,
    CreateStudioCommand,
    CreateTagCommand,
)
from geekbaku.application.catalog.use_cases.create_genre import CreateGenre
from geekbaku.application.catalog.use_cases.create_producer import CreateProducer
from geekbaku.application.catalog.use_cases.create_studio import CreateStudio
from geekbaku.application.catalog.use_cases.create_tag import CreateTag
from geekbaku.application.catalog.use_cases.list_genres import ListGenres
from geekbaku.application.catalog.use_cases.list_producers import ListProducers
from geekbaku.application.catalog.use_cases.list_studios import ListStudios
from geekbaku.application.catalog.use_cases.list_tags import ListTags
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


class TestGenre:
    async def test_creates_and_lists_genres(self) -> None:
        uow = FakeCatalogUnitOfWork()
        await CreateGenre(uow).execute(CreateGenreCommand(name="Shonen", slug="shonen"))

        genres = await ListGenres(uow).execute()

        assert [g.slug for g in genres] == ["shonen"]

    async def test_rejects_duplicate_slug(self) -> None:
        uow = FakeCatalogUnitOfWork()
        command = CreateGenreCommand(name="Shonen", slug="shonen")
        await CreateGenre(uow).execute(command)

        with pytest.raises(DuplicateSlugError):
            await CreateGenre(uow).execute(command)


class TestStudio:
    async def test_creates_and_lists_studios(self) -> None:
        uow = FakeCatalogUnitOfWork()
        await CreateStudio(uow).execute(
            CreateStudioCommand(
                name="MAPPA", slug="mappa", country_code="JP", country_name="Japan"
            )
        )

        studios = await ListStudios(uow).execute()

        assert [s.slug for s in studios] == ["mappa"]
        assert studios[0].country_code == "JP"

    async def test_rejects_duplicate_slug(self) -> None:
        uow = FakeCatalogUnitOfWork()
        command = CreateStudioCommand(name="MAPPA", slug="mappa")
        await CreateStudio(uow).execute(command)

        with pytest.raises(DuplicateSlugError):
            await CreateStudio(uow).execute(command)


class TestProducer:
    async def test_creates_and_lists_producers(self) -> None:
        uow = FakeCatalogUnitOfWork()
        await CreateProducer(uow).execute(
            CreateProducerCommand(
                name="Aniplex", slug="aniplex", country_code="JP", country_name="Japan"
            )
        )

        producers = await ListProducers(uow).execute()

        assert [p.slug for p in producers] == ["aniplex"]
        assert producers[0].country_code == "JP"

    async def test_rejects_duplicate_slug(self) -> None:
        uow = FakeCatalogUnitOfWork()
        command = CreateProducerCommand(name="Aniplex", slug="aniplex")
        await CreateProducer(uow).execute(command)

        with pytest.raises(DuplicateSlugError):
            await CreateProducer(uow).execute(command)


class TestTag:
    async def test_creates_and_lists_tags(self) -> None:
        uow = FakeCatalogUnitOfWork()
        await CreateTag(uow).execute(CreateTagCommand(name="Time Travel", slug="time-travel"))

        tags = await ListTags(uow).execute()

        assert [t.slug for t in tags] == ["time-travel"]

    async def test_rejects_duplicate_slug(self) -> None:
        uow = FakeCatalogUnitOfWork()
        command = CreateTagCommand(name="Time Travel", slug="time-travel")
        await CreateTag(uow).execute(command)

        with pytest.raises(DuplicateSlugError):
            await CreateTag(uow).execute(command)
