"""Schemas Pydantic del catálogo interno. Se traducen a/desde los DTOs de
`application/catalog/dto.py` en los routers — nunca se exponen las
entidades de dominio (`Anime`, `Episode`, ...) directamente.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MediaSchema(BaseModel):
    kind: str = Field(examples=["cover"])
    url: str = Field(examples=["https://cdn.example.com/cover.jpg"])


class ExternalIdSchema(BaseModel):
    source: str = Field(examples=["mal"])
    value: str = Field(examples=["16498"])


class RelationSchema(BaseModel):
    related_anime_id: str
    relation_type: str = Field(examples=["sequel"])


class RatingSchema(BaseModel):
    score: float = Field(examples=[8.5])
    votes: int | None = None
    source: str = Field(examples=["internal"])


class StreamingSourceSchema(BaseModel):
    id: str
    provider_name: str
    external_ref: str
    quality: str = Field(examples=["hd"])
    audio_language: str = Field(examples=["ja"])
    subtitle_language: str | None = None
    url: str | None = None
    is_active: bool


class EpisodeSchema(BaseModel):
    id: str
    number: int = Field(examples=[1])
    title: str = Field(examples=["To You, in 2000 Years"])
    synopsis: str | None = None
    duration_minutes: int | None = Field(default=None, examples=[24])
    air_date: date | None = None
    media: tuple[MediaSchema, ...] = ()
    external_ids: tuple[ExternalIdSchema, ...] = ()
    streaming_sources: tuple[StreamingSourceSchema, ...] = ()


class SeasonSchema(BaseModel):
    id: str
    number: int = Field(examples=[1])
    title: str | None = None
    episodes: tuple[EpisodeSchema, ...] = ()


class AnimeSummarySchema(BaseModel):
    id: str
    title: str = Field(examples=["Shingeki no Kyojin"])
    slug: str = Field(examples=["shingeki-no-kyojin"])
    type: str = Field(examples=["tv"])
    status: str = Field(examples=["ongoing"])
    country_code: str | None = Field(default=None, examples=["JP"])
    thumbnail_url: str | None = None
    rating: RatingSchema | None = None


class AnimeDetailSchema(BaseModel):
    id: str
    title: str
    slug: str
    type: str
    status: str
    synopsis: str | None = None
    country_code: str | None = None
    genre_ids: tuple[str, ...] = ()
    studio_ids: tuple[str, ...] = ()
    producer_ids: tuple[str, ...] = ()
    tag_ids: tuple[str, ...] = ()
    media: tuple[MediaSchema, ...] = ()
    thumbnail_url: str | None = None
    banner_url: str | None = None
    trailer_url: str | None = None
    rating: RatingSchema | None = None
    external_ids: tuple[ExternalIdSchema, ...] = ()
    relations: tuple[RelationSchema, ...] = ()
    seasons: tuple[SeasonSchema, ...] = ()
    created_at: datetime
    updated_at: datetime


class GenreSchema(BaseModel):
    id: str
    name: str = Field(examples=["Action"])
    slug: str = Field(examples=["action"])


class StudioSchema(BaseModel):
    id: str
    name: str = Field(examples=["Wit Studio"])
    slug: str
    country_code: str | None = None


class ProducerSchema(BaseModel):
    id: str
    name: str = Field(examples=["Aniplex"])
    slug: str
    country_code: str | None = None


class TagSchema(BaseModel):
    id: str
    name: str = Field(examples=["time-travel"])
    slug: str


class CatalogFacetsSchema(BaseModel):
    """Estructura de navegación del catálogo interno, para armar filtros."""

    types: tuple[str, ...]
    statuses: tuple[str, ...]
    genres: tuple[GenreSchema, ...]
    studios: tuple[StudioSchema, ...]
    producers: tuple[ProducerSchema, ...]
    tags: tuple[TagSchema, ...]
