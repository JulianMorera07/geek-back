"""Caso de uso: listar los providers registrados en el `ProviderManager`,
con su configuración administrativa y estado observacional en vivo.
"""

from __future__ import annotations

from geekbaku.application.providers.dto import ProviderInfoDTO
from geekbaku.application.providers.manager import ProviderManager


class ListProviders:
    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    async def execute(self) -> list[ProviderInfoDTO]:
        infos = []
        for registration in self._manager.registry.list_all():
            provider = registration.provider
            health = self._manager.get_health(provider.id)
            stats = self._manager.get_stats(provider.id)
            infos.append(
                ProviderInfoDTO(
                    provider_id=str(provider.id),
                    display_name=provider.metadata.display_name,
                    is_enabled=provider.is_enabled,
                    priority=provider.priority,
                    health_status=str(health.status),
                    total_calls=stats.total_calls,
                    successful_calls=stats.successful_calls,
                    failed_calls=stats.failed_calls,
                    average_response_time_ms=stats.average_response_time_ms,
                )
            )
        return infos
