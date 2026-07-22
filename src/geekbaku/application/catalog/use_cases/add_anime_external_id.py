"""Caso de uso: añadir un ExternalId a un Anime."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AddAnimeExternalIdCommand, ExternalIdDTO
from geekbaku.application.catalog.mappers import (
    external_id_to_dto,
    parse_anime_id,
    parse_external_id_source,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import ExternalId


class AddAnimeExternalId:
    """Vincula un Anime con su identificador en un catálogo externo de
    referencia (MAL, AniList, TMDB, ...). Rechaza duplicados por fuente
    (`Anime.add_external_id`).
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: AddAnimeExternalIdCommand) -> ExternalIdDTO:
        anime_id = parse_anime_id(command.anime_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
            if anime is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            external_id = ExternalId(
                source=parse_external_id_source(command.source), value=command.value
            )
            anime.add_external_id(external_id)

            await self._uow.animes.update(anime)
            await self._uow.commit()

        return external_id_to_dto(external_id)
