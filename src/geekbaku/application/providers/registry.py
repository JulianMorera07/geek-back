"""Provider Registry: almacena qué providers están disponibles en runtime.

Responsabilidad única: llevar el registro en memoria de instancias
`ProviderPort` (el adapter) junto con su `StreamingProvider` (config
administrativa: habilitado, prioridad) y, opcionalmente, su
`ProviderConfiguration` (config operacional: rate limit, retry, cache). No
despacha llamadas ni conoce reintentos/cache/salud — eso es responsabilidad
del `ProviderManager` (`application/providers/manager.py`), que usa este
Registry como una de sus piezas.
"""

from __future__ import annotations

from dataclasses import dataclass

from geekbaku.application.providers.ports import ProviderPort
from geekbaku.domain.providers.entities import StreamingProvider
from geekbaku.domain.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
)
from geekbaku.domain.providers.value_objects import (
    ProviderConfiguration,
    ProviderId,
    ProviderMetadata,
)


@dataclass(slots=True)
class ProviderRegistration:
    """Agrupa todo lo que el sistema sabe sobre un provider registrado."""

    provider: StreamingProvider
    adapter: ProviderPort
    configuration: ProviderConfiguration | None = None


class ProviderRegistry:
    """Registro de providers, con soporte para habilitar/deshabilitar y
    ordenar por prioridad (`StreamingProvider.priority`, mayor primero).
    """

    def __init__(self) -> None:
        self._registrations: dict[ProviderId, ProviderRegistration] = {}

    def register(
        self,
        provider_id: ProviderId,
        adapter: ProviderPort,
        *,
        metadata: ProviderMetadata | None = None,
        priority: int = 0,
        is_enabled: bool = True,
        configuration: ProviderConfiguration | None = None,
    ) -> None:
        if provider_id in self._registrations:
            raise ProviderAlreadyRegisteredError(
                f"Ya hay un provider registrado con id '{provider_id}'."
            )
        provider = StreamingProvider(
            id=provider_id,
            metadata=metadata or ProviderMetadata(display_name=str(provider_id)),
            is_enabled=is_enabled,
            priority=priority,
        )
        self._registrations[provider_id] = ProviderRegistration(
            provider=provider, adapter=adapter, configuration=configuration
        )

    def unregister(self, provider_id: ProviderId) -> None:
        if provider_id not in self._registrations:
            raise ProviderNotFoundError(
                f"No hay ningún provider registrado con id '{provider_id}'."
            )
        del self._registrations[provider_id]

    def get(self, provider_id: ProviderId) -> ProviderRegistration:
        try:
            return self._registrations[provider_id]
        except KeyError:
            raise ProviderNotFoundError(
                f"No hay ningún provider registrado con id '{provider_id}'."
            ) from None

    def get_adapter(self, provider_id: ProviderId) -> ProviderPort:
        return self.get(provider_id).adapter

    def enable(self, provider_id: ProviderId) -> None:
        self.get(provider_id).provider.enable()

    def disable(self, provider_id: ProviderId) -> None:
        self.get(provider_id).provider.disable()

    def list_all(self) -> tuple[ProviderRegistration, ...]:
        return tuple(self._registrations.values())

    def list_provider_ids(self) -> tuple[ProviderId, ...]:
        return tuple(self._registrations.keys())

    def list_enabled(self) -> tuple[ProviderRegistration, ...]:
        return tuple(r for r in self._registrations.values() if r.provider.is_enabled)

    def list_enabled_by_priority(self) -> tuple[ProviderRegistration, ...]:
        """Providers habilitados, de mayor a menor prioridad.

        A igualdad de prioridad, se preserva el orden de registro (`sorted`
        es estable), para que el resultado sea determinístico.
        """
        return tuple(
            sorted(self.list_enabled(), key=lambda r: r.provider.priority, reverse=True)
        )
