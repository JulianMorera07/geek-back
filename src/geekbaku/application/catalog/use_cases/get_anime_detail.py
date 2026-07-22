"""Caso de uso: obtener el detalle completo de un Anime por su slug."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AnimeDetailDTO
from geekbaku.application.catalog.mappers import anime_to_detail_dto, parse_slug
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError


class GetAnimeDetail:
    """Recupera un Anime (con sus Seasons/Episodes) a partir de su slug."""

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, slug: str) -> AnimeDetailDTO:
        parsed_slug = parse_slug(slug)

        async with self._uow:
            anime = await self._uow.animes.get_by_slug(parsed_slug)

        if anime is None:
            raise AnimeNotFoundError(f"No existe un anime con el slug '{slug}'.")

        return anime_to_detail_dto(anime)
