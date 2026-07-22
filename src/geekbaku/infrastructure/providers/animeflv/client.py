"""Cliente HTTP crudo de AnimeFLV (https://animeflv.or.at/), un sitio de
scraping (no una API oficial) construido sobre WordPress.

Responsabilidad única: construir URLs, hacer la petición HTTP y devolver
el HTML crudo (`str`) tal como lo entrega el sitio. Este cliente NO conoce
nada de GeekBaku (ni DTOs, ni parsing, ni dominio) — eso vive en
`mapper.py`. No reintenta ni cachea nada por su cuenta: `ProviderManager`
ya se encarga de retry/timeout/circuit breaker/cache de forma genérica
para cualquier provider.

El sitio no expone una API REST: la búsqueda, el catálogo y los "últimos
episodios" son todos la misma ruta (`/`) con distintos query params
(`s`, `anime_page`, `episodes_page`) — un detalle propio de WordPress,
no algo que GeekBaku deba modelar como "endpoints" separados.
"""

from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "https://animeflv.or.at"

#: Algunos hosts de WordPress bloquean o degradan respuestas para clientes
#: sin un User-Agent de navegador. No es una técnica de evasión de nada:
#: es el mismo comportamiento que cualquier navegador real envía.
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class AnimeFlvClient:
    """Wrapper delgado sobre `httpx.AsyncClient` para las páginas de
    AnimeFLV que usa `AnimeFlvProviderAdapter`. El `http_client` se
    inyecta (no lo crea esta clase) para poder interceptarlo con `respx`
    en tests de integración sin hacer peticiones de red reales.
    """

    def __init__(self, http_client: httpx.AsyncClient, base_url: str = DEFAULT_BASE_URL) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")

    async def _get_html(self, path: str, params: dict[str, str | int] | None = None) -> str:
        response = await self._http.get(
            f"{self._base_url}{path}", params=params, headers=_DEFAULT_HEADERS
        )
        response.raise_for_status()
        # El sitio no siempre declara `charset` en el header Content-Type,
        # y httpx cae a un default incorrecto en ese caso (mojibake en
        # acentos/ñ). El HTML sí es UTF-8 (WordPress estándar), así que se
        # fuerza acá en vez de confiar en la detección automática.
        response.encoding = "utf-8"
        return response.text

    async def fetch_home(self) -> str:
        """Home: contiene "Animes en Emisión" (usado como proxy de
        popularidad, ver `mapper.py`) y los primeros "Últimos episodios"."""
        return await self._get_html("/")

    async def fetch_catalog_page(self, page: int) -> str:
        return await self._get_html("/", params={"anime_page": page})

    async def fetch_latest_episodes_page(self, page: int) -> str:
        return await self._get_html("/", params={"episodes_page": page})

    async def fetch_search(self, query: str) -> str:
        return await self._get_html("/", params={"s": query})

    async def fetch_anime_detail(self, slug: str) -> str:
        return await self._get_html(f"/anime/{slug}/")

    async def fetch_url(self, absolute_url: str) -> str:
        """Para páginas de episodio: sus URLs son por fecha
        (`/{año}/{mes}/{día}/{slug}-episodio-{n}/`), no derivables desde
        el slug del anime + número — solo se conocen ya resueltas, desde
        el JSON embebido en la página de detalle (`mapper.parse_episode_refs`).
        """
        response = await self._http.get(absolute_url, headers=_DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text


__all__ = ["DEFAULT_BASE_URL", "AnimeFlvClient"]
