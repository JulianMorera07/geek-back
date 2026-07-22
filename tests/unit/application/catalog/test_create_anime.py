import pytest

from geekbaku.application.catalog.dto import CreateAnimeCommand
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from geekbaku.domain.catalog.value_objects import GenreId, ProducerId, Slug, StudioId, TagId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

pytestmark = pytest.mark.asyncio


def make_command(**overrides: object) -> CreateAnimeCommand:
    defaults: dict[str, object] = {
        "title": "Attack on Titan",
        "slug": "attack-on-titan",
        "type": "tv",
        "status": "ongoing",
        "synopsis": "Humanity fights titans.",
        "country_code": "JP",
        "country_name": "Japan",
    }
    defaults.update(overrides)
    return CreateAnimeCommand(**defaults)  # type: ignore[arg-type]


async def test_creates_anime_and_persists_it() -> None:
    uow = FakeCatalogUnitOfWork()
    use_case = CreateAnime(uow)

    result = await use_case.execute(make_command())

    assert result.title == "Attack on Titan"
    assert result.slug == "attack-on-titan"
    assert result.status == "ongoing"
    assert result.country_code == "JP"
    assert uow.committed is True

    stored = await uow.animes.get_by_slug(Slug("attack-on-titan"))
    assert stored is not None
    assert str(stored.id) == result.id


async def test_rejects_duplicate_slug() -> None:
    uow = FakeCatalogUnitOfWork()
    use_case = CreateAnime(uow)
    await use_case.execute(make_command())

    with pytest.raises(DuplicateSlugError):
        await use_case.execute(make_command(title="Another title"))


async def test_associates_genres_studios_and_tags() -> None:
    uow = FakeCatalogUnitOfWork()
    use_case = CreateAnime(uow)

    genre_id = GenreId.new()
    studio_id = StudioId.new()
    producer_id = ProducerId.new()
    tag_id = TagId.new()

    result = await use_case.execute(
        make_command(
            genre_ids=(str(genre_id),),
            studio_ids=(str(studio_id),),
            producer_ids=(str(producer_id),),
            tag_ids=(str(tag_id),),
        )
    )

    assert result.genre_ids == (str(genre_id),)
    assert result.studio_ids == (str(studio_id),)
    assert result.producer_ids == (str(producer_id),)
    assert result.tag_ids == (str(tag_id),)
