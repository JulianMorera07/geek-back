"""Caso de uso: obtener los géneros que expone un provider."""

from __future__ import annotations

from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_provider_id
from geekbaku.application.providers.normalizers import normalize_genre_names


class GetProviderGenres:
    """A diferencia de `GetProviderCatalog` (que combina géneros y tipos),
    expone solo los géneros, ya normalizados (`normalize_genre_names`).
    """

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, provider_id: str) -> tuple[str, ...]:
        genres = await self._manager.get_genres(parse_provider_id(provider_id))
        return normalize_genre_names(genres)
