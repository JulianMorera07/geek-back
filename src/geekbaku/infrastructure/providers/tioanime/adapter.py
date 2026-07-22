"""Adapter de TioAnime: implementa `ProviderPort` usando `TioAnimeClient`
(I/O crudo) + `mapper` (parsing HTML/JSON + traducción a DTOs). Tercer
proveedor real de GeekBaku (después de Jikan y AnimeFLV), y reemplazo por
defecto de AnimeFLV en `deps.get_provider_manager()` (el sitio de AnimeFLV
dejó de responder) — no le agrega NADA propio de resiliencia
(retry/timeout/circuit breaker/cache), eso lo sigue aplicando
`ProviderManager` de forma genérica.

**Alcance de contenido**: este adapter solo construye requests contra
`tioanime.com` (ver `client.py`) — el dominio hermano de hentai
(`tiohentai.com`) no se referencia en ningún lado del código, y
`mapper.py` descarta defensivamente cualquier género que coincida con
palabras clave de contenido adulto. Doble garantía, no una sola.
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
from geekbaku.infrastructure.providers.tioanime import mapper
from geekbaku.infrastructure.providers.tioanime.client import DEFAULT_BASE_URL, TioAnimeClient

#: Ver `animeflv.adapter._MAX_CONCURRENT_EPISODE_FETCHES` — mismo criterio:
#: acotar cuántas páginas de episodio se scrapean en paralelo dentro de un
#: solo `get_episodes`.
_MAX_CONCURRENT_EPISODE_FETCHES = 5


class TioAnimeProviderAdapter:
    """Implementa `application.providers.ports.ProviderPort` (verificado
    estructuralmente, sin herencia explícita) scrapeando tioanime.com.
    """

    def __init__(
        self,
        client: TioAnimeClient,
        *,
        max_concurrent_episode_fetches: int = _MAX_CONCURRENT_EPISODE_FETCHES,
    ) -> None:
        self._client = client
        self._episode_semaphore = asyncio.Semaphore(max_concurrent_episode_fetches)

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        """`/api/search` no pagina (devuelve todos los matches en una sola
        respuesta) — se pagina del lado del cliente."""
        raw_items = await self._client.search(query)
        items = mapper.parse_search_results(raw_items)
        return _paginate(items, pagination)

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None:
        try:
            html = await self._client.fetch_anime_detail(reference.external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        detail = mapper.parse_anime_detail(html, reference.external_id)
        if any(mapper.is_adult_genre(g) for g in detail.genres):
            # Defensa en profundidad (ver docstring del módulo): nunca se
            # esperaría llegar acá porque tioanime.com no taggea nada así,
            # pero si el sitio cambiara, esto lo trata como "no existe" en
            # vez de servirlo.
            return None
        return detail

    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]:
        html = await self._client.fetch_anime_detail(reference.external_id)
        numbers = mapper.parse_episode_numbers(html)
        episodes = await asyncio.gather(
            *(self._fetch_episode(reference.external_id, number) for number in numbers)
        )
        return sorted(episodes, key=lambda episode: episode.number)

    async def _fetch_episode(self, slug: str, number: int) -> ProviderEpisodeDTO:
        async with self._episode_semaphore:
            html = await self._client.fetch_episode_page(slug, number)
        return mapper.parse_episode_page(html, slug, number)

    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]:
        html = await self._client.fetch_anime_detail(reference.external_id)
        detail = mapper.parse_anime_detail(html, reference.external_id)
        numbers = mapper.parse_episode_numbers(html)
        season = mapper.build_pseudo_season(
            mapper.to_external_reference(reference.external_id), detail.title, len(numbers)
        )
        return [season]

    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]:
        """El sitio sí muestra entregas relacionadas (ej. una película
        previa) en la página de detalle, pero su estructura no se
        investigó en este sprint — devuelve `[]`, documentado como
        limitación honesta, no un `NotImplementedError` (ver
        `docs/adding-a-provider.md`)."""
        return []

    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]:
        html = await self._client.fetch_home()
        items = mapper.parse_latest_episode_items(html)
        return items[: pagination.page_size]

    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]:
        """El sitio no expone un ranking de popularidad real — se usa
        "Últimos Animes" (home) como proxy honesto, mismo criterio que
        `animeflv.adapter.get_popular` usa "Animes en Emisión"."""
        html = await self._client.fetch_home()
        items = mapper.parse_directory_items(html)
        return items[: pagination.page_size]

    async def get_genres(self) -> list[str]:
        html = await self._client.fetch_directory_page(1)
        return mapper.parse_genre_names(html)

    async def get_types(self) -> list[str]:
        return list(mapper.STATIC_ANIME_TYPES)


def _paginate(items: list[SearchResultDTO], pagination: Pagination) -> list[SearchResultDTO]:
    start = (pagination.page - 1) * pagination.page_size
    return items[start : start + pagination.page_size]


def create_tioanime_adapter(configuration: ProviderConfiguration) -> TioAnimeProviderAdapter:
    """Constructor para registrar en `ProviderFactory`:

        factory.register_constructor("tioanime", create_tioanime_adapter)
        adapter = factory.create("tioanime", configuration)
        manager.register(configuration.provider_id, adapter, configuration=configuration)
    """
    http_client = httpx.AsyncClient(timeout=configuration.timeout_seconds)
    base_url = configuration.base_url or DEFAULT_BASE_URL
    client = TioAnimeClient(http_client, base_url=base_url)
    return TioAnimeProviderAdapter(client)


__all__ = ["TioAnimeProviderAdapter", "create_tioanime_adapter"]
