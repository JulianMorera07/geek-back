"""Cliente HTTP crudo de TioAnime (https://tioanime.com/), un sitio de
scraping (no una API oficial) construido sobre un stack propio (no
WordPress, a diferencia de AnimeFLV).

Responsabilidad única: construir URLs, hacer la petición HTTP y devolver
el contenido crudo (HTML como `str`, o el JSON ya parseado para el único
endpoint que lo expone, `/api/search`) tal como lo entrega el sitio. Este
cliente NO conoce nada de GeekBaku (ni DTOs, ni parsing, ni dominio) — eso
vive en `mapper.py`. No reintenta ni cachea nada por su cuenta:
`ProviderManager` ya se encarga de eso de forma genérica.

**Alcance de dominio, a propósito**: este cliente solo construye URLs bajo
`DEFAULT_BASE_URL` (tioanime.com). El sitio enlaza a un dominio separado
de contenido para adultos (`tiohentai.com`, un sitio hermano/afiliado,
completamente distinto); ese dominio NUNCA se referencia acá — no hay
ningún método que apunte a él, ni configuración que lo permita. Es la
garantía estructural de "nada de hentai/adultos" pedida explícitamente:
no depende de un filtro que pueda fallar, depende de que el código
simplemente no sabe que ese dominio existe.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "https://tioanime.com"

JsonList = list[dict[str, Any]]

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class TioAnimeClient:
    """Wrapper delgado sobre `httpx.AsyncClient` para las páginas/endpoint
    de TioAnime que usa `TioAnimeProviderAdapter`. El `http_client` se
    inyecta (no lo crea esta clase) para poder interceptarlo con `respx`
    en tests de integración sin hacer peticiones de red reales.
    """

    def __init__(self, http_client: httpx.AsyncClient, base_url: str = DEFAULT_BASE_URL) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")

    async def _get_html(
        self, path: str, params: dict[str, str | int] | None = None
    ) -> str:
        response = await self._http.get(
            f"{self._base_url}{path}", params=params, headers=_DEFAULT_HEADERS
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text

    async def fetch_home(self) -> str:
        return await self._get_html("/")

    async def fetch_directory_page(
        self, page: int, genero: str | None = None, type_code: int | None = None
    ) -> str:
        params: dict[str, str | int] = {"p": page}
        if genero is not None:
            params["genero"] = genero
        if type_code is not None:
            params["type[]"] = type_code
        return await self._get_html("/directorio", params=params)

    async def fetch_anime_detail(self, slug: str) -> str:
        return await self._get_html(f"/anime/{slug}")

    async def fetch_episode_page(self, slug: str, number: int) -> str:
        return await self._get_html(f"/ver/{slug}-{number}")

    async def search(self, query: str) -> JsonList:
        """`/api/search?value=...` — el único endpoint del sitio que
        devuelve JSON (con `Content-Type: text/html`, un detalle propio
        del sitio; `httpx.Response.json()` lo parsea igual, ignora el
        header)."""
        response = await self._http.get(
            f"{self._base_url}/api/search",
            params={"value": query},
            headers=_DEFAULT_HEADERS,
        )
        response.raise_for_status()
        result: JsonList = response.json()
        return result


__all__ = ["DEFAULT_BASE_URL", "TioAnimeClient"]
