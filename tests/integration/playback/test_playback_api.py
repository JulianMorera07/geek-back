"""Test de integración del Playback API: ejercita la app FastAPI real de
punta a punta (`httpx.AsyncClient` sobre el ASGI app, sin servidor real),
con `app.dependency_overrides` inyectando un `CatalogUnitOfWork` in-memory
(mismo fake que usan los tests unitarios de `catalog`) en vez del adapter
SQLAlchemy real (todavía sin construir). El `PlaybackSessionRepository`
usa su implementación real (`InMemoryPlaybackSessionRepository`), no un
doble: es la misma que se registraría en producción hoy.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from geekbaku.domain.catalog.entities import Anime, Episode, Season, StreamingSource
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    Language,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    Title,
    VideoUrl,
)
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.app import app
from tests.unit.application.catalog.fakes import FakeCatalogUnitOfWork

JAPANESE = Language(code="ja", name="Japanese")


def _make_streaming_source() -> StreamingSource:
    return StreamingSource(
        id=StreamingSourceId.new(),
        provider_name="provider-a",
        external_ref="ep-1",
        quality=StreamQuality.HD,
        audio_language=JAPANESE,
        url=VideoUrl("https://cdn.example.com/ep1.m3u8"),
    )


@pytest.fixture
async def client_with_seeded_catalog() -> AsyncIterator[tuple[AsyncClient, Anime, Episode]]:
    uow = FakeCatalogUnitOfWork()
    anime = Anime(
        id=AnimeId.new(),
        title=Title("Attack on Titan"),
        slug=Slug("attack-on-titan"),
        anime_type=AnimeType.TV,
    )
    season_one = Season(id=SeasonId.new(), number=SeasonNumber(1))
    episode_one = Episode(id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Episode 1"))
    episode_one.add_streaming_source(_make_streaming_source())
    season_one.add_episode(episode_one)
    season_two = Season(id=SeasonId.new(), number=SeasonNumber(2))
    episode_two_one = Episode(
        id=EpisodeId.new(), number=EpisodeNumber(1), title=Title("Season 2 Episode 1")
    )
    season_two.add_episode(episode_two_one)
    anime.add_season(season_one)
    anime.add_season(season_two)
    await uow.animes.add(anime)

    app.dependency_overrides[deps.get_catalog_unit_of_work] = lambda: uow
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, anime, episode_one

    app.dependency_overrides.pop(deps.get_catalog_unit_of_work, None)


class TestGetEpisodePlayback:
    async def test_returns_metadata_and_sources(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, episode = client_with_seeded_catalog

        response = await client.get(f"/api/v1/animes/{anime.id}/episodes/{episode.id}/playback")

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["anime_title"] == "Attack on Titan"
        assert len(body["sources"]) == 1
        assert body["available_qualities"] == ["hd"]

    async def test_returns_404_for_unknown_anime(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, _anime, episode = client_with_seeded_catalog

        response = await client.get(
            f"/api/v1/animes/{AnimeId.new()}/episodes/{episode.id}/playback"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestGetSourcesQualitiesSubtitles:
    async def test_get_sources(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, episode = client_with_seeded_catalog
        response = await client.get(
            f"/api/v1/animes/{anime.id}/episodes/{episode.id}/playback/sources"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_get_qualities(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, episode = client_with_seeded_catalog
        response = await client.get(
            f"/api/v1/animes/{anime.id}/episodes/{episode.id}/playback/qualities"
        )
        assert response.status_code == 200
        assert response.json() == ["hd"]

    async def test_get_subtitles_empty_when_none_available(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, episode = client_with_seeded_catalog
        response = await client.get(
            f"/api/v1/animes/{anime.id}/episodes/{episode.id}/playback/subtitles"
        )
        assert response.status_code == 200
        assert response.json() == []


class TestEpisodeNavigation:
    async def test_next_episode_crosses_season(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, _episode = client_with_seeded_catalog

        response = await client.get(f"/api/v1/animes/{anime.id}/seasons/1/episodes/1/next")

        assert response.status_code == 200
        body = response.json()
        assert body["season_number"] == 2
        assert body["episode_number"] == 1

    async def test_previous_episode_at_start_returns_null(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, anime, _episode = client_with_seeded_catalog

        response = await client.get(f"/api/v1/animes/{anime.id}/seasons/1/episodes/1/previous")

        assert response.status_code == 200
        assert response.json() is None


class TestPlaybackSessionFlow:
    async def test_full_session_lifecycle(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, _anime, episode = client_with_seeded_catalog

        create_response = await client.post(
            "/api/v1/playback/sessions", json={"episode_id": str(episode.id)}
        )
        assert create_response.status_code == 201
        session = create_response.json()
        session_id = session["id"]
        assert session["status"] == "active"

        quality_response = await client.post(
            f"/api/v1/playback/sessions/{session_id}/quality", json={"quality": "fhd"}
        )
        assert quality_response.status_code == 200
        assert quality_response.json()["selected_quality"] == "fhd"

        subtitle_response = await client.post(
            f"/api/v1/playback/sessions/{session_id}/subtitle",
            json={"language_code": "en", "language_name": "English"},
        )
        assert subtitle_response.status_code == 200
        assert subtitle_response.json()["selected_subtitle_language_code"] == "en"

        progress_response = await client.post(
            f"/api/v1/playback/sessions/{session_id}/progress",
            json={"position_seconds": 40, "duration_seconds": 100},
        )
        assert progress_response.status_code == 200
        assert progress_response.json()["progress"]["position_seconds"] == 40

        get_progress_response = await client.get(
            f"/api/v1/playback/sessions/{session_id}/progress"
        )
        assert get_progress_response.status_code == 200
        assert get_progress_response.json()["position_seconds"] == 40

        resume_point_response = await client.get(
            f"/api/v1/playback/sessions/{session_id}/resume-point"
        )
        assert resume_point_response.status_code == 200
        assert resume_point_response.json()["position_seconds"] == 40
        assert resume_point_response.json()["is_completed"] is False

    async def test_progress_for_unknown_session_returns_404(
        self, client_with_seeded_catalog: tuple[AsyncClient, Anime, Episode]
    ) -> None:
        client, _anime, _episode = client_with_seeded_catalog

        response = await client.get(
            "/api/v1/playback/sessions/00000000-0000-0000-0000-000000000000/progress"
        )

        assert response.status_code == 404
