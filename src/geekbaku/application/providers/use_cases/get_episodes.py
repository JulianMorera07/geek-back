"""Caso de uso: obtener los episodios normalizados de un Anime desde un provider."""

from __future__ import annotations

from geekbaku.application.providers.dto import ExternalReferenceDTO, NormalizedEpisodeDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_external_reference
from geekbaku.application.providers.normalizers import to_normalized_episode


class GetProviderEpisodes:
    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, reference: ExternalReferenceDTO) -> tuple[NormalizedEpisodeDTO, ...]:
        parsed_reference = parse_external_reference(reference)
        episodes = await self._manager.get_episodes(parsed_reference)
        return tuple(to_normalized_episode(episode) for episode in episodes)
