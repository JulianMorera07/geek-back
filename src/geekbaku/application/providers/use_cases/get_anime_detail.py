"""Caso de uso: obtener el detalle normalizado de un Anime desde un provider."""

from __future__ import annotations

from geekbaku.application.providers.dto import ExternalReferenceDTO, NormalizedAnimeDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_external_reference
from geekbaku.application.providers.normalizers import to_normalized_anime


class GetProviderAnimeDetail:
    """Obtiene el detalle crudo de un provider y lo normaliza antes de
    devolverlo, para que el consumidor no tenga que conocer el vocabulario
    propio de cada proveedor.
    """

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, reference: ExternalReferenceDTO) -> NormalizedAnimeDTO | None:
        parsed_reference = parse_external_reference(reference)
        provider_anime = await self._manager.get_anime_detail(parsed_reference)
        if provider_anime is None:
            return None
        return to_normalized_anime(provider_anime)
