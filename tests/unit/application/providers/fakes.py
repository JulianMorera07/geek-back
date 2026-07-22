"""Dobles de prueba de `ProviderPort`, usados para ejercitar el
`ProviderManager` y los casos de uso de `application/providers` sin depender
de ningún proveedor real (que no se implementa en este sprint).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.dto import (
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)


class FakeProviderPort:
    """Provider de prueba que devuelve respuestas fijas configurables y
    cuenta cuántas veces se llamó cada método (`call_count`), útil para
    verificar que la cache/rate-limit efectivamente evitan una llamada real.
    """

    def __init__(
        self,
        search_results: list[SearchResultDTO] | None = None,
        latest: list[SearchResultDTO] | None = None,
        popular: list[SearchResultDTO] | None = None,
        genres: list[str] | None = None,
        types: list[str] | None = None,
        anime_detail: ProviderAnimeDTO | None = None,
        episodes: list[ProviderEpisodeDTO] | None = None,
        seasons: list[ProviderSeasonDTO] | None = None,
        related: list[ProviderRelatedDTO] | None = None,
    ) -> None:
        self._search_results = search_results or []
        self._latest = latest or []
        self._popular = popular or []
        self._genres = genres or []
        self._types = types or []
        self._anime_detail = anime_detail
        self._episodes = episodes or []
        self._seasons = seasons or []
        self._related = related or []
        self.call_count: dict[str, int] = defaultdict(int)

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        self.call_count["search"] += 1
        return self._search_results

    async def get_anime_detail(self, reference: object) -> ProviderAnimeDTO | None:
        self.call_count["get_anime_detail"] += 1
        return self._anime_detail

    async def get_episodes(self, reference: object) -> list[ProviderEpisodeDTO]:
        self.call_count["get_episodes"] += 1
        return self._episodes

    async def get_seasons(self, reference: object) -> list[ProviderSeasonDTO]:
        self.call_count["get_seasons"] += 1
        return self._seasons

    async def get_related(self, reference: object) -> list[ProviderRelatedDTO]:
        self.call_count["get_related"] += 1
        return self._related

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        self.call_count["get_latest"] += 1
        return self._latest

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        self.call_count["get_popular"] += 1
        return self._popular

    async def get_genres(self) -> list[str]:
        self.call_count["get_genres"] += 1
        return self._genres

    async def get_types(self) -> list[str]:
        self.call_count["get_types"] += 1
        return self._types


class FailingProviderPort:
    """Provider de prueba que siempre falla, para ejercitar la resiliencia
    del `ProviderManager` ante fallas aisladas de un proveedor.
    """

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        raise RuntimeError("boom")

    async def get_anime_detail(self, reference: object) -> ProviderAnimeDTO | None:
        raise RuntimeError("boom")

    async def get_episodes(self, reference: object) -> list[ProviderEpisodeDTO]:
        raise RuntimeError("boom")

    async def get_seasons(self, reference: object) -> list[ProviderSeasonDTO]:
        raise RuntimeError("boom")

    async def get_related(self, reference: object) -> list[ProviderRelatedDTO]:
        raise RuntimeError("boom")

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise RuntimeError("boom")

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise RuntimeError("boom")

    async def get_genres(self) -> list[str]:
        raise RuntimeError("boom")

    async def get_types(self) -> list[str]:
        raise RuntimeError("boom")


class FlakyProviderPort:
    """Provider de prueba que falla las primeras `fail_times` llamadas a
    `get_genres` y luego responde con éxito. Útil para probar que
    `RetryPolicy` efectivamente reintenta hasta lograr éxito.
    """

    def __init__(self, fail_times: int, genres: list[str] | None = None) -> None:
        self._fail_times = fail_times
        self._genres = genres or []
        self.attempts = 0

    async def get_genres(self) -> list[str]:
        self.attempts += 1
        if self.attempts <= self._fail_times:
            raise RuntimeError(f"boom (intento {self.attempts})")
        return self._genres

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_anime_detail(self, reference: object) -> ProviderAnimeDTO | None:
        raise NotImplementedError

    async def get_episodes(self, reference: object) -> list[ProviderEpisodeDTO]:
        raise NotImplementedError

    async def get_seasons(self, reference: object) -> list[ProviderSeasonDTO]:
        raise NotImplementedError

    async def get_related(self, reference: object) -> list[ProviderRelatedDTO]:
        raise NotImplementedError

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_types(self) -> list[str]:
        raise NotImplementedError


class SlowProviderPort:
    """Provider de prueba cuyo `get_genres` tarda `delay_seconds` en
    responder. Útil para ejercitar el timeout del `ProviderManager`.
    """

    def __init__(self, delay_seconds: float, genres: list[str] | None = None) -> None:
        self._delay_seconds = delay_seconds
        self._genres = genres or []

    async def get_genres(self) -> list[str]:
        await asyncio.sleep(self._delay_seconds)
        return self._genres

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_anime_detail(self, reference: object) -> ProviderAnimeDTO | None:
        raise NotImplementedError

    async def get_episodes(self, reference: object) -> list[ProviderEpisodeDTO]:
        raise NotImplementedError

    async def get_seasons(self, reference: object) -> list[ProviderSeasonDTO]:
        raise NotImplementedError

    async def get_related(self, reference: object) -> list[ProviderRelatedDTO]:
        raise NotImplementedError

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        raise NotImplementedError

    async def get_types(self) -> list[str]:
        raise NotImplementedError
