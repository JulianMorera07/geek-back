"""Caso de uso: vincular dos Anime mediante una relación narrativa."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AddRelationCommand, AnimeDetailDTO
from geekbaku.application.catalog.mappers import (
    anime_to_detail_dto,
    parse_anime_id,
    parse_relation_type,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.services import RelationLinkingService


class AddRelation:
    """Crea una `Relation` entre dos Anime, incluyendo su inversa, de forma
    atómica (afecta a dos agregados dentro de la misma transacción de UoW).
    Ver `RelationLinkingService`.
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: AddRelationCommand) -> AnimeDetailDTO:
        anime_id = parse_anime_id(command.anime_id)
        related_anime_id = parse_anime_id(command.related_anime_id)
        relation_type = parse_relation_type(command.relation_type)

        async with self._uow:
            source = await self._uow.animes.get_by_id(anime_id)
            if source is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            target = await self._uow.animes.get_by_id(related_anime_id)
            if target is None:
                raise AnimeNotFoundError(f"No existe el anime {related_anime_id}.")

            RelationLinkingService.link(source, target, relation_type)

            await self._uow.animes.update(source)
            await self._uow.animes.update(target)
            await self._uow.commit()

        return anime_to_detail_dto(source)
