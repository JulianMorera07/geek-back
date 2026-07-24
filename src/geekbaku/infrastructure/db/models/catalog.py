"""Modelos ORM (SQLAlchemy) del módulo de catálogo.

Mapean las entidades de `domain.catalog.entities` a tablas de Postgres.
Las colecciones de Value Objects que siempre viven embebidas en su
aggregate root (`media`, `external_ids`, `relations` de `Anime`; `media`,
`external_ids` de `Episode`) se persisten como JSONB en vez de tablas
adicionales: nunca se consultan de forma independiente de su dueño, así
que una tabla propia solo agregaría joins sin beneficio real. Las
referencias a otros aggregates (`genre_ids`, `studio_ids`, `producer_ids`,
`tag_ids`) se guardan como `ARRAY(UUID)` por el mismo motivo — filtrar por
contención de array es suficiente para los casos de uso actuales.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from geekbaku.infrastructure.db.base import Base


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)


class StudioModel(Base):
    __tablename__ = "studios"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ProducerModel(Base):
    __tablename__ = "producers"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)


class AnimeModel(Base):
    __tablename__ = "animes"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    synopsis: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    country_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rating_score: Mapped[float | None] = mapped_column(nullable=True)
    rating_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    genre_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )
    studio_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )
    producer_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )
    tag_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list
    )

    media: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    external_ids: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    relations: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    seasons: Mapped[list[SeasonModel]] = relationship(
        back_populates="anime",
        cascade="all, delete-orphan",
        order_by="SeasonModel.number",
        lazy="selectin",
    )


class SeasonModel(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("anime_id", "number", name="uq_season_anime_number"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    anime_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("animes.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    anime: Mapped[AnimeModel] = relationship(back_populates="seasons")
    episodes: Mapped[list[EpisodeModel]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
        order_by="EpisodeModel.number",
        lazy="selectin",
    )


class EpisodeModel(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("season_id", "number", name="uq_episode_season_number"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    season_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    media: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    external_ids: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    season: Mapped[SeasonModel] = relationship(back_populates="episodes")
    streaming_sources: Mapped[list[StreamingSourceModel]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class StreamingSourceModel(Base):
    __tablename__ = "streaming_sources"
    __table_args__ = (
        UniqueConstraint(
            "episode_id",
            "provider_name",
            "external_ref",
            name="uq_streaming_source_episode_provider_ref",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    audio_language_code: Mapped[str] = mapped_column(String(2), nullable=False)
    audio_language_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle_language_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    subtitle_language_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    episode: Mapped[EpisodeModel] = relationship(back_populates="streaming_sources")


__all__ = [
    "AnimeModel",
    "EpisodeModel",
    "GenreModel",
    "ProducerModel",
    "SeasonModel",
    "StreamingSourceModel",
    "StudioModel",
    "TagModel",
]
