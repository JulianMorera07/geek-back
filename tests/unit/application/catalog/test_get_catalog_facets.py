import pytest

from geekbaku.application.catalog.dto import CreateGenreCommand, CreateStudioCommand
from geekbaku.application.catalog.use_cases.create_genre import CreateGenre
from geekbaku.application.catalog.use_cases.create_studio import CreateStudio
from geekbaku.application.catalog.use_cases.get_catalog_facets import GetCatalogFacets
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_includes_static_types_and_statuses() -> None:
    uow = FakeCatalogUnitOfWork()

    facets = await GetCatalogFacets(uow).execute()

    assert "tv" in facets.types
    assert "ongoing" in facets.statuses


async def test_includes_created_genres_and_studios() -> None:
    uow = FakeCatalogUnitOfWork()
    await CreateGenre(uow).execute(CreateGenreCommand(name="Shonen", slug="shonen"))
    await CreateStudio(uow).execute(CreateStudioCommand(name="MAPPA", slug="mappa"))

    facets = await GetCatalogFacets(uow).execute()

    assert [g.slug for g in facets.genres] == ["shonen"]
    assert [s.slug for s in facets.studios] == ["mappa"]
    assert facets.producers == ()
    assert facets.tags == ()
