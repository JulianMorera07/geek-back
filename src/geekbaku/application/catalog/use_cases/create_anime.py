"""Caso de uso: crear un nuevo Anime en el catálogo."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AnimeDetailDTO, CreateAnimeCommand
from geekbaku.application.catalog.mappers import (
    anime_to_detail_dto,
    parse_anime_status,
    parse_anime_type,
    parse_genre_id,
    parse_producer_id,
    parse_slug,
    parse_studio_id,
    parse_tag_id,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import Anime
from geekbaku.domain.catalog.exceptions import DuplicateSlugError
from geekbaku.domain.catalog.value_objects import AnimeId, Country, Synopsis, Title


class CreateAnime:
    """Registra un nuevo Anime en el catálogo.

    No valida que los `genre_ids`/`studio_ids`/`tag_ids` recibidos existan
    en sus repositorios: se mantiene este caso de uso simple y esa
    validación cruzada se puede añadir después sin romper la firma pública.
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: CreateAnimeCommand) -> AnimeDetailDTO:
        slug = parse_slug(command.slug)

        async with self._uow:
            if await self._uow.animes.exists_by_slug(slug):
                raise DuplicateSlugError(f"Ya existe un anime con el slug '{slug}'.")

            country = (
                Country(code=command.country_code, name=command.country_name)
                if command.country_code and command.country_name
                else None
            )

            anime = Anime(
                id=AnimeId.new(),
                title=Title(command.title),
                slug=slug,
                anime_type=parse_anime_type(command.type),
                status=parse_anime_status(command.status),
                synopsis=Synopsis(command.synopsis) if command.synopsis else None,
                country=country,
            )

            for genre_id in command.genre_ids:
                anime.add_genre(parse_genre_id(genre_id))
            for studio_id in command.studio_ids:
                anime.add_studio(parse_studio_id(studio_id))
            for producer_id in command.producer_ids:
                anime.add_producer(parse_producer_id(producer_id))
            for tag_id in command.tag_ids:
                anime.add_tag(parse_tag_id(tag_id))

            await self._uow.animes.add(anime)
            await self._uow.commit()

        return anime_to_detail_dto(anime)
