"""Caso de uso: filtrar un conjunto de resultados ya obtenidos.

No consulta ningún provider: recibe resultados ya resueltos (por
`SearchAnime`, `GetLatest`, `GetPopular`, ...) y los acota en memoria. Existe
como caso de uso independiente porque no todos los providers soportan
filtros finos en su propia API (algunos solo saben "traer los últimos N"),
así que el afinado por tipo/año/provider queda de nuestro lado.
"""

from __future__ import annotations

from geekbaku.application.providers.dto import SearchResultDTO


class FilterSearchResults:
    def execute(
        self,
        results: list[SearchResultDTO],
        anime_type: str | None = None,
        year: int | None = None,
        provider_id: str | None = None,
    ) -> list[SearchResultDTO]:
        filtered = results
        if anime_type is not None:
            filtered = [r for r in filtered if r.anime_type == anime_type]
        if year is not None:
            filtered = [r for r in filtered if r.year == year]
        if provider_id is not None:
            filtered = [r for r in filtered if r.provider_id == provider_id]
        return filtered
