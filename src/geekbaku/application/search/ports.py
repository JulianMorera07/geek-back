"""Puerto de búsqueda sobre el catálogo interno persistido.

Distinto del `ProviderPort.search` (`application/providers/ports.py`): este
puerto busca dentro de LO YA PERSISTIDO en GeekBaku (nuestro propio catálogo,
`AnimeRepository`), mientras que el motor de providers busca en fuentes
externas en vivo. Un adapter concreto (Postgres full-text search,
Meilisearch, etc.) se implementará en un sprint futuro cuando exista un caso
de uso que lo consuma; el contrato se fija ahora para no bloquear ese trabajo.
"""

from __future__ import annotations

from typing import Protocol

from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.catalog.value_objects import AnimeId


class SearchRepository(Protocol):
    """Busca Anime en el catálogo interno por texto libre."""

    async def search_anime(
        self, query: str, pagination: Pagination
    ) -> tuple[list[AnimeId], int]:
        """Devuelve (ids de la página de resultados, total sin paginar)."""
        ...
