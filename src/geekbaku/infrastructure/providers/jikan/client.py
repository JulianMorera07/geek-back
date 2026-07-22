"""Cliente HTTP crudo de la API pública de Jikan v4 (https://docs.api.jikan.moe/),
un wrapper REST no oficial sobre MyAnimeList.

Responsabilidad única: construir URLs, hacer la petición HTTP y devolver el
JSON crudo (`dict`) tal como lo entrega Jikan. Este cliente NO conoce nada
de GeekBaku (ni DTOs ni dominio) — esa traducción vive en `mapper.py`. No
reintenta ni cachea nada por su cuenta: `ProviderManager` ya se encarga de
retry/timeout/circuit breaker/cache de forma genérica para cualquier
provider, así que duplicar esa lógica acá sería redundante.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.jikan.moe/v4"

JsonDict = dict[str, Any]


class JikanClient:
    """Wrapper delgado sobre `httpx.AsyncClient` para los endpoints de Jikan
    que usa `JikanProviderAdapter`. El `http_client` se inyecta (no lo crea
    esta clase) para poder interceptarlo con `respx` en tests de integración
    sin hacer peticiones de red reales.
    """

    def __init__(self, http_client: httpx.AsyncClient, base_url: str = DEFAULT_BASE_URL) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")

    async def _get(self, path: str, params: JsonDict | None = None) -> JsonDict:
        response = await self._http.get(f"{self._base_url}{path}", params=params)
        response.raise_for_status()
        result: JsonDict = response.json()
        return result

    async def search_anime(self, query: str, page: int, limit: int) -> JsonDict:
        return await self._get("/anime", params={"q": query, "page": page, "limit": limit})

    async def get_anime_full(self, mal_id: str) -> JsonDict:
        return await self._get(f"/anime/{mal_id}/full")

    async def get_anime_episodes(self, mal_id: str, page: int = 1) -> JsonDict:
        return await self._get(f"/anime/{mal_id}/episodes", params={"page": page})

    async def get_anime_relations(self, mal_id: str) -> JsonDict:
        return await self._get(f"/anime/{mal_id}/relations")

    async def get_seasons_now(self, page: int, limit: int) -> JsonDict:
        return await self._get("/seasons/now", params={"page": page, "limit": limit})

    async def get_top_anime(self, page: int, limit: int) -> JsonDict:
        return await self._get("/top/anime", params={"page": page, "limit": limit})

    async def get_genres(self) -> JsonDict:
        return await self._get("/genres/anime")
