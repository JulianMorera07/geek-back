"""Adapter de Jikan: implementa `ProviderPort` usando `JikanClient` (I/O
crudo) + `mapper` (traducción a DTOs). Es el primer proveedor real de
GeekBaku, construido con la arquitectura del Provider Framework
(`application/providers/`): no le agrega NADA propio de resiliencia
(retry/timeout/circuit breaker/cache) — todo eso lo aplica `ProviderManager`
de forma genérica sobre cualquier provider registrado.

Toda la información que sale de acá ya pasó por `mapper.py`: en ningún
punto se devuelve el JSON crudo de Jikan hacia quien llame a este adapter.
"""

from __future__ import annotations

import httpx

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.dto import (
    ProviderAnimeDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderConfiguration
from geekbaku.infrastructure.providers.jikan import mapper
from geekbaku.infrastructure.providers.jikan.client import DEFAULT_BASE_URL, JikanClient


class JikanProviderAdapter:
    """Implementa `application.providers.ports.ProviderPort` (verificado
    estructuralmente, sin herencia explícita) contra la API pública de
    Jikan v4.
    """

    def __init__(self, client: JikanClient) -> None:
        self._client = client

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        raw = await self._client.search_anime(query, pagination.page, pagination.page_size)
        return [mapper.map_search_result(item) for item in raw.get("data", [])]

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None:
        try:
            raw = await self._client.get_anime_full(reference.external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return mapper.map_anime_detail(raw["data"])

    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]:
        raw = await self._client.get_anime_episodes(reference.external_id)
        return [
            mapper.map_episode(item, reference.external_id) for item in raw.get("data", [])
        ]

    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]:
        raw = await self._client.get_anime_full(reference.external_id)
        reference_dto = mapper.to_external_reference(reference.external_id)
        return [mapper.map_season(raw["data"], reference_dto)]

    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]:
        raw = await self._client.get_anime_relations(reference.external_id)
        related: list[ProviderRelatedDTO] = []
        for group in raw.get("data", []):
            related.extend(mapper.map_relation_group(group))
        return related

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        raw = await self._client.get_seasons_now(pagination.page, pagination.page_size)
        return [mapper.map_search_result(item) for item in raw.get("data", [])]

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        raw = await self._client.get_top_anime(pagination.page, pagination.page_size)
        return [mapper.map_search_result(item) for item in raw.get("data", [])]

    async def get_genres(self) -> list[str]:
        raw = await self._client.get_genres()
        return mapper.map_genre_names(raw)

    async def get_types(self) -> list[str]:
        return list(mapper.STATIC_ANIME_TYPES)


def create_jikan_adapter(configuration: ProviderConfiguration) -> JikanProviderAdapter:
    """Constructor para registrar en `ProviderFactory`:

        factory.register_constructor("jikan", create_jikan_adapter)
        adapter = factory.create("jikan", configuration)
        manager.register(configuration.provider_id, adapter, configuration=configuration)

    El `httpx.AsyncClient` resultante queda con el mismo timeout que
    `ProviderManager` aplica vía `asyncio.wait_for` (doble protección: si
    algún día se llama a `JikanClient` fuera del Manager, sigue teniendo un
    timeout propio).
    """
    http_client = httpx.AsyncClient(timeout=configuration.timeout_seconds)
    base_url = configuration.base_url or DEFAULT_BASE_URL
    client = JikanClient(http_client, base_url=base_url)
    return JikanProviderAdapter(client)
