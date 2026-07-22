"""Caso de uso: obtener las temporadas normalizadas de un Anime desde un provider."""

from __future__ import annotations

from geekbaku.application.providers.dto import ExternalReferenceDTO, NormalizedSeasonDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_external_reference
from geekbaku.application.providers.normalizers import to_normalized_season


class GetProviderSeasons:
    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, reference: ExternalReferenceDTO) -> tuple[NormalizedSeasonDTO, ...]:
        parsed_reference = parse_external_reference(reference)
        seasons = await self._manager.get_seasons(parsed_reference)
        return tuple(to_normalized_season(season) for season in seasons)
