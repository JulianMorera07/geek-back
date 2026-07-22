"""Caso de uso: obtener el detalle completo de un Anime por su id.

Complementa a `GetAnimeDetail` (por slug, pensado para URLs legibles del
frontend): este es el que usa la API pública para `GET /api/v1/anime/{id}`.
"""

from __future__ import annotations

from geekbaku.application.catalog.dto import AnimeDetailDTO
from geekbaku.application.catalog.mappers import anime_to_detail_dto, parse_anime_id
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


class GetAnimeById:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, anime_id: str) -> AnimeDetailDTO:
        parsed_id = parse_anime_id(anime_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(parsed_id)

        if anime is None:
            raise AnimeNotFoundError(f"No existe un anime con id '{anime_id}'.")

        return anime_to_detail_dto(anime)
