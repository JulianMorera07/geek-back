"""Caso de uso: obtener las fuentes de reproducción activas de un Episode."""

from __future__ import annotations

from geekbaku.application.catalog.dto import StreamingSourceDTO
from geekbaku.application.catalog.mappers import parse_episode_id, streaming_source_to_dto
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.exceptions import EpisodeNotFoundError
from geekbaku.domain.catalog.services import EpisodeAvailabilityService
from geekbaku.domain.catalog.value_objects import STREAM_QUALITY_RANK


class GetEpisodeSources:
    """Devuelve las `StreamingSource` activas de un Episode, ordenadas de
    mayor a menor calidad, usando `EpisodeAvailabilityService`.

    Devuelve una tupla vacía si el episodio no tiene ninguna fuente activa
    (no es un error de negocio: un episodio puede existir sin fuentes
    disponibles todavía, ej. antes de que un provider lo indexe).
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, episode_id: str) -> tuple[StreamingSourceDTO, ...]:
        parsed_id = parse_episode_id(episode_id)

        async with self._uow:
            episode = await self._uow.episodes.get_by_id(parsed_id)

        if episode is None:
            raise EpisodeNotFoundError(f"No existe el episodio {episode_id}.")

        if not EpisodeAvailabilityService.is_available(episode):
            return ()

        active_sources = sorted(
            (source for source in episode.streaming_sources if source.is_active),
            key=lambda source: STREAM_QUALITY_RANK[source.quality],
            reverse=True,
        )
        return tuple(streaming_source_to_dto(source) for source in active_sources)
