"""Caso de uso: añadir una StreamingSource a un Episode."""

from __future__ import annotations

from geekbaku.application.catalog.dto import AddStreamingSourceCommand, StreamingSourceDTO
from geekbaku.application.catalog.mappers import (
    parse_anime_id,
    parse_episode_id,
    parse_stream_quality,
    streaming_source_to_dto,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.domain.catalog.entities import StreamingSource
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError
from geekbaku.domain.catalog.value_objects import Language, StreamingSourceId, VideoUrl


class AddStreamingSource:
    """Agrega una fuente de reproducción a un Episode.

    Rechaza fuentes duplicadas para el mismo `(provider_name, external_ref)`
    (`Episode.add_streaming_source`).
    """

    def __init__(self, uow: CatalogUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: AddStreamingSourceCommand) -> StreamingSourceDTO:
        anime_id = parse_anime_id(command.anime_id)
        episode_id = parse_episode_id(command.episode_id)

        async with self._uow:
            anime = await self._uow.animes.get_by_id(anime_id)
            if anime is None:
                raise AnimeNotFoundError(f"No existe el anime {anime_id}.")

            episode = anime.find_episode(episode_id)

            subtitle_language = (
                Language(command.subtitle_language_code, command.subtitle_language_name)
                if command.subtitle_language_code and command.subtitle_language_name
                else None
            )

            source = StreamingSource(
                id=StreamingSourceId.new(),
                provider_name=command.provider_name,
                external_ref=command.external_ref,
                quality=parse_stream_quality(command.quality),
                audio_language=Language(
                    command.audio_language_code, command.audio_language_name
                ),
                subtitle_language=subtitle_language,
                url=VideoUrl(command.url) if command.url else None,
            )
            episode.add_streaming_source(source)

            await self._uow.animes.update(anime)
            await self._uow.commit()

        return streaming_source_to_dto(source)
