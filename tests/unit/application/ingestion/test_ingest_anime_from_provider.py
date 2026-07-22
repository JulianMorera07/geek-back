import pytest

from geekbaku.application.ingestion.dto import IngestAnimeCommand
from geekbaku.application.ingestion.use_cases.ingest_anime_from_provider import (
    IngestAnimeFromProvider,
)
from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderSourceDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_ID = ProviderId("animeflv")


def make_manager(
    anime_detail: ProviderAnimeDTO | None, episodes: list[ProviderEpisodeDTO]
) -> ProviderManager:
    manager = ProviderManager()
    manager.register(
        PROVIDER_ID,
        FakeProviderPort(anime_detail=anime_detail, episodes=episodes),
    )
    return manager


def make_provider_anime(external_id: str = "example-anime") -> ProviderAnimeDTO:
    return ProviderAnimeDTO(
        reference=ExternalReferenceDTO(provider_id="animeflv", external_id=external_id),
        title="Example Anime",
        synopsis="Una sinopsis de ejemplo.",
        genres=("Comedia", "Seinen"),
    )


def make_provider_episode(number: int = 1) -> ProviderEpisodeDTO:
    return ProviderEpisodeDTO(
        reference=ExternalReferenceDTO(
            provider_id="animeflv", external_id=f"example-anime:{number}"
        ),
        number=number,
        title=f"Example Anime Episodio {number}",
        sources=(
            ProviderSourceDTO(
                url="https://mega.nz/file/example",
                quality="MP4",
                subtitle_language_code="es",
            ),
            ProviderSourceDTO(
                url="https://www.mp4upload.com/example",
                quality="MP4",
                audio_language_code="es",
            ),
        ),
    )


class TestIngestAnimeFromProvider:
    async def test_ingests_anime_with_episodes_and_sources(self) -> None:
        uow = FakeCatalogUnitOfWork()
        manager = make_manager(make_provider_anime(), [make_provider_episode(1)])
        use_case = IngestAnimeFromProvider(uow, manager)

        result = await use_case.execute(
            IngestAnimeCommand(provider_id="animeflv", external_id="example-anime")
        )

        assert result.title == "Example Anime"
        assert result.synopsis == "Una sinopsis de ejemplo."
        assert len(result.seasons) == 1
        assert len(result.seasons[0].episodes) == 1

        episode = result.seasons[0].episodes[0]
        assert episode.number == 1
        assert len(episode.streaming_sources) == 2

    async def test_maps_audio_and_subtitle_languages(self) -> None:
        uow = FakeCatalogUnitOfWork()
        manager = make_manager(make_provider_anime(), [make_provider_episode(1)])
        use_case = IngestAnimeFromProvider(uow, manager)

        result = await use_case.execute(
            IngestAnimeCommand(provider_id="animeflv", external_id="example-anime")
        )

        sources = result.seasons[0].episodes[0].streaming_sources
        subbed = next(s for s in sources if s.subtitle_language is not None)
        dubbed = next(s for s in sources if s.subtitle_language is None)

        assert subbed.audio_language == "ja"
        assert subbed.subtitle_language == "es"
        assert dubbed.audio_language == "es"

    async def test_creates_genres_that_do_not_exist_yet(self) -> None:
        uow = FakeCatalogUnitOfWork()
        manager = make_manager(make_provider_anime(), [])
        use_case = IngestAnimeFromProvider(uow, manager)

        result = await use_case.execute(
            IngestAnimeCommand(provider_id="animeflv", external_id="example-anime")
        )

        assert len(result.genre_ids) == 2
        stored_genres = await uow.genres.list_all()
        assert {g.name for g in stored_genres} == {"Comedia", "Seinen"}

    async def test_second_call_returns_existing_anime_without_calling_provider_again(
        self,
    ) -> None:
        uow = FakeCatalogUnitOfWork()
        manager = make_manager(make_provider_anime(), [make_provider_episode(1)])
        use_case = IngestAnimeFromProvider(uow, manager)
        command = IngestAnimeCommand(provider_id="animeflv", external_id="example-anime")

        first = await use_case.execute(command)
        second = await use_case.execute(command)

        assert first.id == second.id
        adapter = manager.registry.get_adapter(PROVIDER_ID)
        assert isinstance(adapter, FakeProviderPort)
        assert adapter.call_count["get_anime_detail"] == 1

    async def test_raises_when_provider_has_no_such_anime(self) -> None:
        uow = FakeCatalogUnitOfWork()
        manager = make_manager(anime_detail=None, episodes=[])
        use_case = IngestAnimeFromProvider(uow, manager)

        with pytest.raises(AnimeNotFoundError):
            await use_case.execute(
                IngestAnimeCommand(provider_id="animeflv", external_id="does-not-exist")
            )
