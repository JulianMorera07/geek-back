"""Puertos (interfaces) del módulo de catálogo.

Estas interfaces (`Protocol`, PEP 544) son implementadas por adapters
concretos en `infrastructure/` (fuera del alcance de este sprint). Los casos
de uso dependen exclusivamente de estas abstracciones.
"""

from __future__ import annotations

from typing import Protocol

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.common.unit_of_work import UnitOfWork
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Producer, Studio, Tag
from geekbaku.domain.catalog.value_objects import (
    AnimeFilter,
    AnimeId,
    EpisodeId,
    GenreId,
    ProducerId,
    Slug,
    StudioId,
    TagId,
)


class AnimeRepository(Protocol):
    """Repositorio del Aggregate Root `Anime` (incluye Seasons/Episodes)."""

    async def get_by_id(self, anime_id: AnimeId) -> Anime | None: ...

    async def get_by_slug(self, slug: Slug) -> Anime | None: ...

    async def exists_by_slug(self, slug: Slug) -> bool: ...

    async def list(
        self, filters: AnimeFilter, pagination: Pagination
    ) -> tuple[list[Anime], int]:
        """Devuelve (items de la página, total de resultados sin paginar)."""
        ...

    async def add(self, anime: Anime) -> None: ...

    async def update(self, anime: Anime) -> None: ...


class EpisodeRepository(Protocol):
    """Repositorio de solo lectura para acceder a un Episode sin cargar todo
    el agregado `Anime`, útil para casos de uso enfocados en reproducción
    (ej. `GetEpisodeSources`).
    """

    async def get_by_id(self, episode_id: EpisodeId) -> Episode | None: ...


class GenreRepository(Protocol):
    async def get_by_id(self, genre_id: GenreId) -> Genre | None: ...

    async def get_by_slug(self, slug: Slug) -> Genre | None: ...

    async def get_many_by_ids(self, genre_ids: set[GenreId]) -> list[Genre]: ...

    async def exists_by_slug(self, slug: Slug) -> bool: ...

    async def list_all(self) -> list[Genre]: ...

    async def add(self, genre: Genre) -> None: ...


class StudioRepository(Protocol):
    async def get_by_id(self, studio_id: StudioId) -> Studio | None: ...

    async def get_by_slug(self, slug: Slug) -> Studio | None: ...

    async def get_many_by_ids(self, studio_ids: set[StudioId]) -> list[Studio]: ...

    async def exists_by_slug(self, slug: Slug) -> bool: ...

    async def list_all(self) -> list[Studio]: ...

    async def add(self, studio: Studio) -> None: ...


class ProducerRepository(Protocol):
    async def get_by_id(self, producer_id: ProducerId) -> Producer | None: ...

    async def get_by_slug(self, slug: Slug) -> Producer | None: ...

    async def get_many_by_ids(self, producer_ids: set[ProducerId]) -> list[Producer]: ...

    async def exists_by_slug(self, slug: Slug) -> bool: ...

    async def list_all(self) -> list[Producer]: ...

    async def add(self, producer: Producer) -> None: ...


class TagRepository(Protocol):
    async def get_by_id(self, tag_id: TagId) -> Tag | None: ...

    async def get_by_slug(self, slug: Slug) -> Tag | None: ...

    async def get_many_by_ids(self, tag_ids: set[TagId]) -> list[Tag]: ...

    async def exists_by_slug(self, slug: Slug) -> bool: ...

    async def list_all(self) -> list[Tag]: ...

    async def add(self, tag: Tag) -> None: ...


class CatalogRepository(Protocol):
    """Puerto de lectura para vistas agregadas/denormalizadas del catálogo
    interno persistido (ej. últimos agregados, más populares), complementario
    a `AnimeRepository` (que se enfoca en CRUD sobre el agregado `Anime`).

    El criterio de "popular" depende de métricas que todavía no existen en
    el sistema (reproducciones, favoritos: módulos de sprints futuros); este
    puerto define el contrato desde ya para que ese módulo, cuando exista,
    solo tenga que implementar el adapter, sin tocar casos de uso.
    """

    async def list_latest(self, pagination: Pagination) -> tuple[list[Anime], int]: ...

    async def list_popular(self, pagination: Pagination) -> tuple[list[Anime], int]: ...


class CatalogUnitOfWork(UnitOfWork, Protocol):
    """Unit of Work del módulo de catálogo: agrupa sus repositorios para que
    los casos de uso que tocan más de un agregado (ej. `AddRelation`, que
    escribe dos `Anime`) lo hagan de forma atómica.
    """

    animes: AnimeRepository
    episodes: EpisodeRepository
    genres: GenreRepository
    studios: StudioRepository
    producers: ProducerRepository
    tags: TagRepository
