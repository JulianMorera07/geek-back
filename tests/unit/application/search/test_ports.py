from geekbaku.application.common.pagination import Pagination
from geekbaku.application.search.ports import SearchRepository
from geekbaku.domain.catalog.value_objects import AnimeId


class InMemorySearchRepository:
    """Doble mínimo que satisface `SearchRepository` estructuralmente."""

    def __init__(self, ids: list[AnimeId]) -> None:
        self._ids = ids

    async def search_anime(
        self, query: str, pagination: Pagination
    ) -> tuple[list[AnimeId], int]:
        start = pagination.offset
        end = start + pagination.limit
        return self._ids[start:end], len(self._ids)


async def test_search_repository_returns_paginated_ids() -> None:
    anime_id = AnimeId.new()
    repository: SearchRepository = InMemorySearchRepository([anime_id])

    ids, total = await repository.search_anime("attack", Pagination())

    assert ids == [anime_id]
    assert total == 1


async def test_empty_repository_returns_no_results() -> None:
    repository: SearchRepository = InMemorySearchRepository([])

    ids, total = await repository.search_anime("attack", Pagination())

    assert ids == []
    assert total == 0
