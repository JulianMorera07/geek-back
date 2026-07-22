"""Puertos del módulo de providers.

`ProviderPort` es LA interfaz que todo proveedor de streaming debe
implementar para poder registrarse en el `ProviderRegistry`
(`application/providers/registry.py`) y ser orquestado por el
`ProviderManager` (`application/providers/manager.py`). Es el contrato
central de este sprint: el dominio y la aplicación no conocen ni dependen de
ningún proveedor concreto, solo de esta abstracción.

`ProviderRepository` persiste la configuración administrativa
(`StreamingProvider`: qué providers existen, si están habilitados, con qué
prioridad) — un concepto distinto y desacoplado del `ProviderPort`, que es
el adapter en tiempo de ejecución.
"""

from __future__ import annotations

from typing import Protocol

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.dto import (
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)
from geekbaku.domain.providers.entities import StreamingProvider
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId


class ProviderPort(Protocol):
    """Contrato único que implementa cada proveedor de streaming.

    Cada método corresponde a una de las capacidades de adquisición de datos
    que el sistema debe soportar (Search, Detail, Episodes, Seasons, Genres,
    Popular, Latest, Related). Un adapter concreto (ej. para "provider_a") no
    se implementa en este sprint: solo se define y se ejercita esta interfaz
    con dobles de prueba.
    """

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]: ...

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None: ...

    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]: ...

    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]: ...

    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]: ...

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]: ...

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]: ...

    async def get_genres(self) -> list[str]: ...

    async def get_types(self) -> list[str]: ...


class ProviderRepository(Protocol):
    """Persiste el registro/configuración administrativa de providers
    (`StreamingProvider`: habilitado, prioridad)."""

    async def get_by_id(self, provider_id: ProviderId) -> StreamingProvider | None: ...

    async def list_all(self) -> list[StreamingProvider]: ...

    async def list_enabled(self) -> list[StreamingProvider]: ...

    async def add(self, provider: StreamingProvider) -> None: ...

    async def update(self, provider: StreamingProvider) -> None: ...
