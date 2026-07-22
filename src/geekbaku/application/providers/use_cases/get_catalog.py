"""Caso de uso: obtener las facetas de catálogo (géneros/tipos) de un provider."""

from __future__ import annotations

from geekbaku.application.providers.dto import ProviderCatalogDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_provider_id


class GetProviderCatalog:
    """Combina `ProviderPort.get_genres` y `ProviderPort.get_types` en una
    sola respuesta, útil para poblar filtros de navegación por provider.
    """

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, provider_id: str) -> ProviderCatalogDTO:
        return await self._manager.get_catalog(parse_provider_id(provider_id))
