from geekbaku.application.playback.session_store import InMemoryPlaybackSessionRepository
from geekbaku.domain.catalog.value_objects import EpisodeId
from geekbaku.domain.playback.entities import PlaybackSession
from geekbaku.domain.playback.value_objects import PlaybackSessionId


class TestInMemoryPlaybackSessionRepository:
    async def test_returns_none_for_unknown_session(self) -> None:
        repository = InMemoryPlaybackSessionRepository()
        assert await repository.get_by_id(PlaybackSessionId.new()) is None

    async def test_add_and_get(self) -> None:
        repository = InMemoryPlaybackSessionRepository()
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())

        await repository.add(session)

        assert await repository.get_by_id(session.id) is session

    async def test_update_persists_mutations(self) -> None:
        repository = InMemoryPlaybackSessionRepository()
        session = PlaybackSession(id=PlaybackSessionId.new(), episode_id=EpisodeId.new())
        await repository.add(session)

        session.pause()
        await repository.update(session)

        stored = await repository.get_by_id(session.id)
        assert stored is not None
        assert stored.status.value == "paused"
