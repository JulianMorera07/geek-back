import pytest

from geekbaku.application.catalog.dto import (
    AddEpisodeCommand,
    AddRelationCommand,
    AddSeasonCommand,
    AddStreamingSourceCommand,
    CreateAnimeCommand,
)
from geekbaku.application.catalog.use_cases.add_episode import AddEpisode
from geekbaku.application.catalog.use_cases.add_relation import AddRelation
from geekbaku.application.catalog.use_cases.add_season import AddSeason
from geekbaku.application.catalog.use_cases.add_streaming_source import AddStreamingSource
from geekbaku.application.catalog.use_cases.create_anime import CreateAnime
from geekbaku.domain.catalog.exceptions import DuplicateStreamingSourceError, SelfRelationError
from geekbaku.domain.catalog.value_objects import RelationType, Slug
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


def _source_command(
    anime_id: str, episode_id: str, **overrides: object
) -> AddStreamingSourceCommand:
    defaults: dict[str, object] = {
        "anime_id": anime_id,
        "episode_id": episode_id,
        "provider_name": "provider_a",
        "external_ref": "ep-1",
        "quality": "hd",
        "audio_language_code": "ja",
        "audio_language_name": "Japanese",
    }
    defaults.update(overrides)
    return AddStreamingSourceCommand(**defaults)  # type: ignore[arg-type]


class TestAddStreamingSource:
    async def test_adds_streaming_source(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, episode_id = await _create_anime_with_episode(uow)

        result = await AddStreamingSource(uow).execute(_source_command(anime_id, episode_id))

        assert result.provider_name == "provider_a"
        assert result.quality == "hd"
        assert result.is_active is True

    async def test_rejects_duplicate_provider_and_ref(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime_id, episode_id = await _create_anime_with_episode(uow)
        command = _source_command(anime_id, episode_id)
        await AddStreamingSource(uow).execute(command)

        with pytest.raises(DuplicateStreamingSourceError):
            await AddStreamingSource(uow).execute(command)


class TestAddRelation:
    async def test_links_two_animes_with_inverse_relation(self) -> None:
        uow = FakeCatalogUnitOfWork()
        source = await CreateAnime(uow).execute(
            CreateAnimeCommand(title="Attack on Titan", slug="aot", type="tv", status="completed")
        )
        target = await CreateAnime(uow).execute(
            CreateAnimeCommand(
                title="Attack on Titan S2", slug="aot-s2", type="tv", status="completed"
            )
        )

        detail = await AddRelation(uow).execute(
            AddRelationCommand(
                anime_id=source.id, related_anime_id=target.id, relation_type="sequel"
            )
        )

        assert len(detail.relations) == 1
        assert detail.relations[0].related_anime_id == target.id
        assert detail.relations[0].relation_type == "sequel"

        source_anime = await uow.animes.get_by_slug(Slug("aot"))
        target_anime = await uow.animes.get_by_slug(Slug("aot-s2"))
        assert source_anime is not None
        assert target_anime is not None
        assert target_anime.relations[0].related_anime_id == source_anime.id
        assert target_anime.relations[0].relation_type == RelationType.PREQUEL

    async def test_rejects_self_relation(self) -> None:
        uow = FakeCatalogUnitOfWork()
        anime = await CreateAnime(uow).execute(
            CreateAnimeCommand(title="Frieren", slug="frieren", type="tv", status="ongoing")
        )

        with pytest.raises(SelfRelationError):
            await AddRelation(uow).execute(
                AddRelationCommand(
                    anime_id=anime.id, related_anime_id=anime.id, relation_type="sequel"
                )
            )
