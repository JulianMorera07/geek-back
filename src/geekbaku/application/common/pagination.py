"""Paginación genérica, reutilizable por cualquier módulo de aplicación."""

from __future__ import annotations

from dataclasses import dataclass

_MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class Pagination:
    """Parámetros de paginación de entrada (1-indexed)."""

    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page debe ser >= 1.")
        if not (1 <= self.page_size <= _MAX_PAGE_SIZE):
            raise ValueError(f"page_size debe estar entre 1 y {_MAX_PAGE_SIZE}.")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Resultado paginado de salida."""

    items: tuple[T, ...]
    total: int
    page: int
    page_size: int
