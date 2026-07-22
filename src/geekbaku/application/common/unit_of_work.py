"""Puerto genérico de Unit of Work.

Cada módulo de aplicación (catalog, auth, ...) define su propia extensión
de `UnitOfWork` exponiendo los repositorios que necesita (ver
`geekbaku.application.catalog.ports.CatalogUnitOfWork`). Los casos de uso
dependen únicamente de estas interfaces, nunca de una implementación
concreta (SQLAlchemy, in-memory, etc.), que se resuelve en
`geekbaku.composition`.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    """Delimita una transacción atómica sobre uno o más repositorios."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
