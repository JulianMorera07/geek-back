"""Caso de uso: listar todos los Producer disponibles."""

from __future__ import annotations

from geekbaku.application.catalog.dto import ProducerDTO
from geekbaku.application.catalog.mappers import producer_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork


class ListProducers:
    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self) -> tuple[ProducerDTO, ...]:
        async with self._uow:
            producers = await self._uow.producers.list_all()

        return tuple(producer_to_dto(producer) for producer in producers)
