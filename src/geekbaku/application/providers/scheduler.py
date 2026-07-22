"""Scheduler: diseño para futuras sincronizaciones automáticas.

Este módulo define la FORMA de una sincronización periódica
(`SyncJobDefinition`) y el puerto que un scheduler real implementaría
(`SyncSchedulerPort`), más un registro en memoria (`InMemorySyncJobRegistry`)
para poder describir/inspeccionar/testear jobs sin ejecutar nada.

Deliberadamente NO hay cron, ni un loop en background, ni integración con
APScheduler/Celery Beat en este sprint ("no implementar cron todavía"). Un
sprint futuro implementará `SyncSchedulerPort` con un scheduler real que,
periódicamente, invoque al `ProviderManager` (ej. `get_latest`) y pase el
resultado a la capa de ingesta del catálogo interno (tampoco implementada
todavía).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from geekbaku.domain.providers.value_objects import ProviderId
from geekbaku.domain.shared.errors import ValidationError

#: Operaciones del `ProviderManager` que tiene sentido sincronizar
#: periódicamente. No incluye operaciones dirigidas a un contenido puntual
#: (`get_anime_detail`, `get_episodes`, ...), que se disparan bajo demanda.
SYNCABLE_OPERATIONS = frozenset({"latest", "popular", "genres", "types"})


@dataclass(frozen=True, slots=True)
class SyncJobDefinition:
    """Describe una sincronización periódica con un provider.

    Es solo datos: no se ejecuta a sí misma. `interval_seconds` es la
    cadencia deseada; la traducción a una expresión cron concreta (o a lo
    que use el scheduler real) queda para cuando exista esa implementación.
    """

    provider_id: ProviderId
    operation: str
    interval_seconds: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.operation not in SYNCABLE_OPERATIONS:
            raise ValidationError(
                f"'{self.operation}' no es una operación sincronizable "
                f"(válidas: {sorted(SYNCABLE_OPERATIONS)})."
            )
        if self.interval_seconds <= 0:
            raise ValidationError("interval_seconds debe ser mayor a 0.")


class SyncSchedulerPort(Protocol):
    """Puerto para un futuro scheduler real (cron, APScheduler, Celery Beat).

    Sin implementación en este sprint: ningún adapter concreto ejecuta estos
    jobs todavía.
    """

    async def schedule(self, job: SyncJobDefinition) -> None: ...

    async def unschedule(self, provider_id: ProviderId, operation: str) -> None: ...

    async def list_jobs(self) -> list[SyncJobDefinition]: ...


class InMemorySyncJobRegistry:
    """Registro en memoria de `SyncJobDefinition`.

    Permite describir/inspeccionar la configuración deseada de
    sincronización (y testearla) sin depender de un scheduler real. No
    dispara ninguna llamada a ningún provider por sí mismo.
    """

    def __init__(self) -> None:
        self._jobs: dict[tuple[ProviderId, str], SyncJobDefinition] = {}

    def add(self, job: SyncJobDefinition) -> None:
        self._jobs[(job.provider_id, job.operation)] = job

    def remove(self, provider_id: ProviderId, operation: str) -> None:
        self._jobs.pop((provider_id, operation), None)

    def get(self, provider_id: ProviderId, operation: str) -> SyncJobDefinition | None:
        return self._jobs.get((provider_id, operation))

    def list_all(self) -> tuple[SyncJobDefinition, ...]:
        return tuple(self._jobs.values())

    def list_enabled(self) -> tuple[SyncJobDefinition, ...]:
        return tuple(job for job in self._jobs.values() if job.enabled)
