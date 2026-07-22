"""Adapter de AnimeFLV: implementa `ProviderPort` usando `AnimeFlvClient`
(I/O crudo) + `mapper` (parsing HTML + traducción a DTOs). No le agrega
NADA propio de resiliencia (retry/timeout/circuit breaker/cache) — todo
eso lo aplica `ProviderManager` de forma genérica sobre cualquier
provider registrado, exactamente igual que con Jikan.

Segundo proveedor real de GeekBaku (después de Jikan/MAL, Sprint 5), y el
primero basado en scraping en vez de una API oficial — el contrato
`ProviderPort` no distingue entre ambos: para el resto del sistema
(`ProviderManager`, `AggregationEngine`, la API pública), scraping vs. API
oficial es un detalle de implementación invisible.
"""

from __future__ import annotations

import asyncio

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
from geekbaku.infrastructure.providers.animeflv import mapper
from geekbaku.infrastructure.providers.animeflv.client import DEFAULT_BASE_URL, AnimeFlvClient

#: Límite de páginas de episodio scrapeadas en paralelo dentro de un solo
#: `get_episodes`. El sitio no tiene un endpoint que devuelva servidores
#: de todos los episodios de una vez (cada episodio es su propia página),
#: así que `get_episodes` completo hace 1 request (detalle del anime, para
#: la lista de episodios) + N requests (una por episodio, para sus
#: servidores) — este semáforo evita floodear el sitio cuando N es alto.
#: El costo se paga una vez por TTL de cache (`ProviderManager` cachea el
#: resultado completo de `get_episodes`), no en cada request a la API.
_MAX_CONCURRENT_EPISODE_FETCHES = 5


class AnimeFlvProviderAdapter:
    """Implementa `application.providers.ports.ProviderPort` (verificado
    estructuralmente, sin herencia explícita) scrapeando animeflv.or.at.
    """

    def __init__(
        self,
        client: AnimeFlvClient,
        *,
        max_concurrent_episode_fetches: int = _MAX_CONCURRENT_EPISODE_FETCHES,
    ) -> None:
        self._client = client
        self._episode_semaphore = asyncio.Semaphore(max_concurrent_episode_fetches)

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        """El sitio no pagina resultados de búsqueda del lado del
        servidor (`?s=` devuelve una sola página) — se pagina del lado
        del cliente sobre lo que el sitio ya devolvió."""
        html = await self._client.fetch_search(query)
        items = mapper.parse_search_results(html)
        return _paginate(items, pagination)

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None:
        try:
            html = await self._client.fetch_anime_detail(reference.external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return mapper.parse_anime_detail(html, reference.external_id)

    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]:
        html = await self._client.fetch_anime_detail(reference.external_id)
        refs = mapper.parse_episode_refs(html)
        episodes = await asyncio.gather(
            *(self._fetch_episode(reference.external_id, ref) for ref in refs)
        )
        return sorted(episodes, key=lambda episode: episode.number)

    async def _fetch_episode(self, anime_slug: str, ref: dict[str, object]) -> ProviderEpisodeDTO:
        permalink = str(ref.get("permalink", ""))
        raw_number = ref.get("number")
        number = int(raw_number) if isinstance(raw_number, (int, float, str)) else 0
        post_id = ref.get("post_id")
        async with self._episode_semaphore:
            html = await self._client.fetch_url(permalink)
        return mapper.parse_episode_page(html, anime_slug, post_id, number)

    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]:
        html = await self._client.fetch_anime_detail(reference.external_id)
        detail = mapper.parse_anime_detail(html, reference.external_id)
        refs = mapper.parse_episode_refs(html)
        season = mapper.build_pseudo_season(
            mapper.to_external_reference(reference.external_id), detail.title, len(refs)
        )
        return [season]

    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]:
        """El sitio no expone relaciones entre animes (secuelas,
        spin-offs, ...): cada temporada/entrega es un slug de catálogo
        independiente, sin cross-links navegables. Devuelve siempre una
        lista vacía — decisión documentada, no un `NotImplementedError`
        (ver `docs/adding-a-provider.md`)."""
        return []

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        html = await self._client.fetch_latest_episodes_page(pagination.page)
        items = mapper.parse_latest_episode_items(html)
        return _paginate(items, pagination, already_offset=True)

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        """El sitio no expone un ranking real de popularidad (ni vistas
        ni votos ordenables) — se usa "Animes en Emisión" (home) como
        proxy honesto: es lo más cercano a "lo que se está mirando ahora"
        que el sitio publica. Documentado explícitamente, no una
        suposición silenciosa."""
        html = await self._client.fetch_home()
        items = mapper.parse_listing_items(html)
        return _paginate(items, pagination)

    async def get_genres(self) -> list[str]:
        """Best-effort: agrega los géneros vistos en la primera página
        del catálogo (el sitio no expone una taxonomía separada, ver
        `mapper.parse_genre_names`)."""
        html = await self._client.fetch_catalog_page(1)
        return mapper.parse_genre_names(html)

    async def get_types(self) -> list[str]:
        return list(mapper.STATIC_ANIME_TYPES)


def _paginate(
    items: list[SearchResultDTO], pagination: Pagination, *, already_offset: bool = False
) -> list[SearchResultDTO]:
    if already_offset:
        return items[: pagination.page_size]
    start = (pagination.page - 1) * pagination.page_size
    return items[start : start + pagination.page_size]


def create_animeflv_adapter(configuration: ProviderConfiguration) -> AnimeFlvProviderAdapter:
    """Constructor para registrar en `ProviderFactory`:

        factory.register_constructor("animeflv", create_animeflv_adapter)
        adapter = factory.create("animeflv", configuration)
        manager.register(configuration.provider_id, adapter, configuration=configuration)

    El `httpx.AsyncClient` resultante queda con el mismo timeout que
    `ProviderManager` aplica vía `asyncio.wait_for` (doble protección).
    """
    http_client = httpx.AsyncClient(timeout=configuration.timeout_seconds)
    base_url = configuration.base_url or DEFAULT_BASE_URL
    client = AnimeFlvClient(http_client, base_url=base_url)
    return AnimeFlvProviderAdapter(client)


__all__ = ["AnimeFlvProviderAdapter", "create_animeflv_adapter"]
