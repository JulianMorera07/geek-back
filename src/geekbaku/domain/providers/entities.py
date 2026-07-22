"""Entidades del módulo de providers."""

from __future__ import annotations

from datetime import UTC, datetime

from geekbaku.domain.providers.value_objects import ProviderId, ProviderMetadata, ProviderStatus


class StreamingProvider:
    """Registro de un proveedor de streaming dentro de GeekBaku.

    Representa la CONFIGURACIÓN persistida de un provider (habilitado o no,
    prioridad de despacho), no la implementación en sí: la implementación
    concreta (el adapter que sabe hablar con el sitio externo) es un
    `ProviderPort` registrado en el `ProviderRegistry` en tiempo de ejecución
    (`application/providers/registry.py`). Esta entidad es lo que persiste
    `ProviderRepository`.
    """

    def __init__(
        self,
        id: ProviderId,
        metadata: ProviderMetadata,
        is_enabled: bool = True,
        priority: int = 0,
    ) -> None:
        self.id = id
        self.metadata = metadata
        self.is_enabled = is_enabled
        self.priority = priority

    def enable(self) -> None:
        self.is_enabled = True

    def disable(self) -> None:
        self.is_enabled = False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StreamingProvider) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


#: Fallas consecutivas a partir de las cuales un provider pasa a DEGRADED / DOWN.
_DEFAULT_DEGRADED_AFTER = 1
_DEFAULT_DOWN_AFTER = 3


class ProviderHealth:
    """Estado operacional observado de un provider, actualizado en cada
    llamada real (éxito o falla) por el `ProviderManager`.

    Regla de negocio: un provider pasa a `DEGRADED` en la primera falla y a
    `DOWN` tras `down_after` fallas consecutivas; cualquier éxito lo vuelve a
    `HEALTHY` y reinicia el contador. Es información para PRIORIZAR (ej.
    excluir providers `DOWN` de un fan-out agregado), no un circuit breaker
    que bloquee llamadas dirigidas a un provider específico.
    """

    def __init__(self, provider_id: ProviderId) -> None:
        self.provider_id = provider_id
        self.status = ProviderStatus.UNKNOWN
        self.consecutive_failures = 0
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.last_checked_at: datetime | None = None

    def record_success(self) -> None:
        now = datetime.now(UTC)
        self.status = ProviderStatus.HEALTHY
        self.consecutive_failures = 0
        self.last_error = None
        self.last_success_at = now
        self.last_checked_at = now

    def record_failure(
        self,
        error: str,
        *,
        degraded_after: int = _DEFAULT_DEGRADED_AFTER,
        down_after: int = _DEFAULT_DOWN_AFTER,
    ) -> None:
        self.consecutive_failures += 1
        self.last_error = error
        self.last_checked_at = datetime.now(UTC)
        if self.consecutive_failures >= down_after:
            self.status = ProviderStatus.DOWN
        elif self.consecutive_failures >= degraded_after:
            self.status = ProviderStatus.DEGRADED

    def is_available(self) -> bool:
        return self.status != ProviderStatus.DOWN

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ProviderHealth) and self.provider_id == other.provider_id

    def __hash__(self) -> int:
        return hash(self.provider_id)
