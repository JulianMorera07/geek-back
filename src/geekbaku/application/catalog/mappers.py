"""Mappers del módulo de catálogo.

Traducen en ambas direcciones entre el dominio (entidades / value objects) y
los DTOs/commands de la capa de aplicación:

- `parse_*`: primitivos de un Command/Query -> Value Objects de dominio.
  Cualquier `ValueError`/`KeyError` de conversión (UUID inválido, enum
  desconocido) se traduce a `ValidationError` de dominio.
- `*_to_dto`: entidades de dominio -> DTOs de salida (solo primitivos).

Ningún caso de uso debe construir un DTO ni un Value Object "a mano": siempre
pasa por estas funciones, para que la traducción quede en un único lugar.
"""

from __future__ import annotations

from uuid import UUID

from geekbaku.application.catalog.dto import (
    AnimeDetailDTO,
    AnimeSummaryDTO,
    EpisodeDTO,
    ExternalIdDTO,
    GenreDTO,
    MediaDTO,
    ProducerDTO,
    RatingDTO,
    RelationDTO,
    SeasonDTO,
    StreamingSourceDTO,
    StudioDTO,
    TagDTO,
)
from geekbaku.domain.catalog.entities import (
    Anime,
    Episode,
    Genre,
    Producer,
    Season,
    StreamingSource,
    Studio,
    Tag,
)
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeStatus,
    AnimeType,
    EpisodeId,
    EpisodeNumber,
    ExternalId,
    ExternalIdSource,
    GenreId,
    Media,
    ProducerId,
    Rating,
    Relation,
    RelationType,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    StudioId,
    TagId,
)
from geekbaku.domain.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Parsing: primitivos -> Value Objects
# ---------------------------------------------------------------------------


def _parse_uuid(value: str, *, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError(f"'{value}' no es un UUID válido para '{field_name}'.") from exc


def parse_anime_id(value: str) -> AnimeId:
    return AnimeId(_parse_uuid(value, field_name="anime_id"))


def parse_season_id(value: str) -> SeasonId:
    return SeasonId(_parse_uuid(value, field_name="season_id"))


def parse_episode_id(value: str) -> EpisodeId:
    return EpisodeId(_parse_uuid(value, field_name="episode_id"))


def parse_genre_id(value: str) -> GenreId:
    return GenreId(_parse_uuid(value, field_name="genre_id"))


def parse_studio_id(value: str) -> StudioId:
    return StudioId(_parse_uuid(value, field_name="studio_id"))


def parse_producer_id(value: str) -> ProducerId:
    return ProducerId(_parse_uuid(value, field_name="producer_id"))


def parse_tag_id(value: str) -> TagId:
    return TagId(_parse_uuid(value, field_name="tag_id"))


def parse_streaming_source_id(value: str) -> StreamingSourceId:
    return StreamingSourceId(_parse_uuid(value, field_name="streaming_source_id"))


def parse_slug(value: str) -> Slug:
    return Slug(value)


def parse_season_number(value: int) -> SeasonNumber:
    return SeasonNumber(value)


def parse_episode_number(value: int) -> EpisodeNumber:
    return EpisodeNumber(value)


def parse_anime_type(value: str) -> AnimeType:
    try:
        return AnimeType(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un AnimeType válido.") from exc


def parse_anime_status(value: str) -> AnimeStatus:
    try:
        return AnimeStatus(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un AnimeStatus válido.") from exc


def parse_external_id_source(value: str) -> ExternalIdSource:
    try:
        return ExternalIdSource(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un ExternalIdSource válido.") from exc


def parse_relation_type(value: str) -> RelationType:
    try:
        return RelationType(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un RelationType válido.") from exc


def parse_stream_quality(value: str) -> StreamQuality:
    try:
        return StreamQuality(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un StreamQuality válido.") from exc


# ---------------------------------------------------------------------------
# Domain -> DTO
# ---------------------------------------------------------------------------


def media_to_dto(media: Media) -> MediaDTO:
    return MediaDTO(kind=str(media.kind), url=media.url)


def external_id_to_dto(external_id: ExternalId) -> ExternalIdDTO:
    return ExternalIdDTO(source=str(external_id.source), value=external_id.value)


def relation_to_dto(relation: Relation) -> RelationDTO:
    return RelationDTO(
        related_anime_id=str(relation.related_anime_id),
        relation_type=str(relation.relation_type),
    )


def rating_to_dto(rating: Rating) -> RatingDTO:
    return RatingDTO(score=rating.score, votes=rating.votes, source=rating.source)


def streaming_source_to_dto(source: StreamingSource) -> StreamingSourceDTO:
    return StreamingSourceDTO(
        id=str(source.id),
        provider_name=source.provider_name,
        external_ref=source.external_ref,
        quality=str(source.quality),
        audio_language=source.audio_language.code,
        subtitle_language=source.subtitle_language.code if source.subtitle_language else None,
        url=source.url.value if source.url else None,
        is_active=source.is_active,
    )


def episode_to_dto(episode: Episode) -> EpisodeDTO:
    return EpisodeDTO(
        id=str(episode.id),
        number=episode.number.value,
        title=str(episode.title),
        synopsis=str(episode.synopsis) if episode.synopsis else None,
        duration_minutes=episode.duration.minutes if episode.duration else None,
        air_date=episode.air_date,
        media=tuple(media_to_dto(m) for m in episode.media),
        external_ids=tuple(external_id_to_dto(e) for e in episode.external_ids),
        streaming_sources=tuple(streaming_source_to_dto(s) for s in episode.streaming_sources),
    )


def season_to_dto(season: Season) -> SeasonDTO:
    return SeasonDTO(
        id=str(season.id),
        number=season.number.value,
        title=season.title,
        episodes=tuple(episode_to_dto(e) for e in season.episodes),
    )


def anime_to_summary_dto(anime: Anime) -> AnimeSummaryDTO:
    return AnimeSummaryDTO(
        id=str(anime.id),
        title=str(anime.title),
        slug=str(anime.slug),
        type=str(anime.type),
        status=str(anime.status),
        country_code=anime.country.code if anime.country else None,
        thumbnail_url=anime.thumbnail.url.value if anime.thumbnail else None,
        rating=rating_to_dto(anime.rating) if anime.rating else None,
    )


def anime_to_detail_dto(anime: Anime) -> AnimeDetailDTO:
    return AnimeDetailDTO(
        id=str(anime.id),
        title=str(anime.title),
        slug=str(anime.slug),
        type=str(anime.type),
        status=str(anime.status),
        synopsis=str(anime.synopsis) if anime.synopsis else None,
        country_code=anime.country.code if anime.country else None,
        genre_ids=tuple(str(g) for g in anime.genre_ids),
        studio_ids=tuple(str(s) for s in anime.studio_ids),
        producer_ids=tuple(str(p) for p in anime.producer_ids),
        tag_ids=tuple(str(t) for t in anime.tag_ids),
        media=tuple(media_to_dto(m) for m in anime.media),
        thumbnail_url=anime.thumbnail.url.value if anime.thumbnail else None,
        banner_url=anime.banner.url.value if anime.banner else None,
        trailer_url=anime.trailer.url.value if anime.trailer else None,
        rating=rating_to_dto(anime.rating) if anime.rating else None,
        external_ids=tuple(external_id_to_dto(e) for e in anime.external_ids),
        relations=tuple(relation_to_dto(r) for r in anime.relations),
        seasons=tuple(season_to_dto(s) for s in anime.seasons),
        created_at=anime.created_at,
        updated_at=anime.updated_at,
    )


def genre_to_dto(genre: Genre) -> GenreDTO:
    return GenreDTO(id=str(genre.id), name=genre.name, slug=str(genre.slug))


def studio_to_dto(studio: Studio) -> StudioDTO:
    return StudioDTO(
        id=str(studio.id),
        name=studio.name,
        slug=str(studio.slug),
        country_code=studio.country.code if studio.country else None,
    )


def producer_to_dto(producer: Producer) -> ProducerDTO:
    return ProducerDTO(
        id=str(producer.id),
        name=producer.name,
        slug=str(producer.slug),
        country_code=producer.country.code if producer.country else None,
    )


def tag_to_dto(tag: Tag) -> TagDTO:
    return TagDTO(id=str(tag.id), name=tag.name, slug=str(tag.slug))
