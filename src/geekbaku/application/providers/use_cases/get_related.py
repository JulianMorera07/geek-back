"""Caso de uso: obtener información relacionada (anime relacionados) desde un provider."""

from __future__ import annotations

from geekbaku.application.providers.dto import ExternalReferenceDTO, NormalizedRelatedDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_external_reference
from geekbaku.application.providers.normalizers import to_normalized_related


class GetProviderRelated:
    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self, reference: ExternalReferenceDTO) -> tuple[NormalizedRelatedDTO, ...]:
        parsed_reference = parse_external_reference(reference)
        related = await self._manager.get_related(parsed_reference)
        return tuple(to_normalized_related(item) for item in related)
