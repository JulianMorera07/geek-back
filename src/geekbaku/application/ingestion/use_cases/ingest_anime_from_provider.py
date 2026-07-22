"""Caso de uso: traer un Anime (detalle + episodios + fuentes de
streaming) desde un provider externo y persistirlo en el catálogo interno
la primera vez que se pide — así el resto del sistema (detalle,
episodios, Playback Engine) puede servirlo igual que a cualquier `Anime`
creado a mano.

Es la pieza que faltaba entre el Provider Framework/Aggregation Engine
(que solo devuelven DTOs efímeros, nunca persisten nada) y el catálogo
interno: `application/providers/normalizers.py` ya dejaba documentado que
"esa coincidencia/creación es responsabilidad de una futura capa de
ingesta" — este módulo es esa capa.
"""

from __future__ import annotations

import re

from geekbaku.application.catalog.dto import AnimeDetailDTO
from geekbaku.application.catalog.mappers import (
    anime_to_detail_dto,
    parse_anime_status,
    parse_anime_type,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.ingestion.dto import IngestAnimeCommand
from geekbaku.application.providers.dto import ProviderSourceDTO
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.normalizers import slugify, to_normalized_anime
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Season, StreamingSource
from geekbaku.domain.catalog.exceptions import AnimeNotFoundError as InternalAnimeNotFoundError
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    EpisodeId,
    EpisodeNumber,
    GenreId,
    Language,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    Synopsis,
    Title,
    VideoUrl,
)
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId

#: AnimeFLV (y cualquier scraper futuro) no expone una resolución real por
#: fuente, solo el formato del archivo ("MP4") — se infiere una calidad
#: aproximada a partir de palabras clave en esa etiqueta, con HD como
#: default razonable (no hay forma de saber más sin descargar el archivo).
_QUALITY_KEYWORDS: tuple[tuple[str, StreamQuality], ...] = (
    ("4k", StreamQuality.UHD),
    ("uhd", StreamQuality.UHD),
    ("2160", StreamQuality.UHD),
    ("1080", StreamQuality.FHD),
    ("fhd", StreamQuality.FHD),
    ("480", StreamQuality.SD),
    ("360", StreamQuality.SD),
    ("sd", StreamQuality.SD),
)

_JAPANESE = Language(code="ja", name="Japanese")
_LATIN_SPANISH = Language(code="es", name="Español")

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def _normalize_quality(raw: str) -> StreamQuality:
    lowered = raw.lower()
    for keyword, quality in _QUALITY_KEYWORDS:
        if keyword in lowered:
            return quality
    return StreamQuality.HD


def _audio_language(source: ProviderSourceDTO) -> Language:
    if source.audio_language_code == "es":
        return _LATIN_SPANISH
    return _JAPANESE


def _subtitle_language(source: ProviderSourceDTO) -> Language | None:
    if source.subtitle_language_code == "es":
        return _LATIN_SPANISH
    return None


def _to_streaming_source(provider_id: str, source: ProviderSourceDTO) -> StreamingSource:
    return StreamingSource(
        id=StreamingSourceId.new(),
        provider_name=provider_id,
        external_ref=source.url,
        quality=_normalize_quality(source.quality),
        audio_language=_audio_language(source),
        subtitle_language=_subtitle_language(source),
        url=VideoUrl(source.url),
    )


def _build_slug(provider_id: str, external_id: str) -> Slug:
    raw = f"{provider_id}-{external_id}"
    cleaned = _NON_SLUG_CHARS.sub("-", slugify(raw)).strip("-")
    return Slug(cleaned or "untitled")


class IngestAnimeFromProvider:
    def __init__(self, uow: CatalogUnitOfWork, provider_manager: ProviderManager) -> None:
        self._uow = uow
        self._manager = provider_manager

    async def execute(self, command: IngestAnimeCommand) -> AnimeDetailDTO:
        slug = _build_slug(command.provider_id, command.external_id)

        async with self._uow:
            existing = await self._uow.animes.get_by_slug(slug)
            if existing is not None:
                return anime_to_detail_dto(existing)

        reference = ExternalReference(
            provider_id=ProviderId(command.provider_id), external_id=command.external_id
        )
        provider_anime = await self._manager.get_anime_detail(reference)
        if provider_anime is None:
            raise InternalAnimeNotFoundError(
                f"El provider '{command.provider_id}' no tiene un anime con id "
                f"'{command.external_id}'."
            )
        provider_episodes = await self._manager.get_episodes(reference)
        normalized = to_normalized_anime(provider_anime)

        async with self._uow:
            # Re-chequea por si otro request ingestó el mismo anime mientras
            # se esperaban las llamadas al provider (evita duplicados ante
            # dos clicks casi simultáneos sobre el mismo resultado).
            existing = await self._uow.animes.get_by_slug(slug)
            if existing is not None:
                return anime_to_detail_dto(existing)

            anime = Anime(
                id=AnimeId.new(),
                title=Title(normalized.title),
                slug=slug,
                anime_type=parse_anime_type(normalized.type),
                status=parse_anime_status(normalized.status),
                synopsis=Synopsis(normalized.synopsis) if normalized.synopsis else None,
            )

            for genre_name in normalized.genres:
                genre = await self._get_or_create_genre(genre_name)
                anime.add_genre(genre.id)

            season = Season(id=SeasonId.new(), number=SeasonNumber(1))
            for provider_episode in provider_episodes:
                episode = Episode(
                    id=EpisodeId.new(),
                    number=EpisodeNumber(provider_episode.number),
                    title=Title(provider_episode.title or f"Episodio {provider_episode.number}"),
                )
                for source in provider_episode.sources:
                    episode.add_streaming_source(
                        _to_streaming_source(command.provider_id, source)
                    )
                season.add_episode(episode)
            anime.add_season(season)

            await self._uow.animes.add(anime)
            await self._uow.commit()

        return anime_to_detail_dto(anime)

    async def _get_or_create_genre(self, name: str) -> Genre:
        genre_slug = Slug(slugify(name))
        existing = await self._uow.genres.get_by_slug(genre_slug)
        if existing is not None:
            return existing
        genre = Genre(id=GenreId.new(), name=name, slug=genre_slug)
        await self._uow.genres.add(genre)
        return genre


__all__ = ["IngestAnimeFromProvider"]
