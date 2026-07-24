"""Adapter SQLAlchemy de `CatalogUnitOfWork`: reemplaza el default en
memoria (`InMemoryCatalogUnitOfWork`) con persistencia real en Postgres.

Las colecciones de Value Objects embebidos (`media`, `external_ids`,
`relations`) se serializan a/desde JSONB; las referencias a otros
aggregates (`genre_ids`, etc.) a/desde `ARRAY(UUID)`. Ver el docstring de
`infrastructure.db.models.catalog` para el razonamiento.

Los mappers `_anime_to_model`/`_model_to_anime` (y sus equivalentes para
`Season`/`Episode`/`StreamingSource`) hidratan directamente los atributos
"privados" de las entidades (ej. `anime._genre_ids = ...`) en vez de usar
los mutadores públicos (`add_genre`, ...): los mutadores llaman `_touch()`
y reasignarían `updated_at` en cada lectura, corrompiendo el dato real.
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Self

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from geekbaku.application.catalog.ports import (
    AnimeRepository,
    EpisodeRepository,
    GenreRepository,
    ProducerRepository,
    StudioRepository,
    TagRepository,
)
from geekbaku.application.common.pagination import Pagination
from geekbaku.domain.catalog.entities import Anime, Episode, Genre, Producer, Season, Studio, Tag
from geekbaku.domain.catalog.entities import StreamingSource as StreamingSourceEntity
from geekbaku.domain.catalog.value_objects import (
    AnimeFilter,
    AnimeId,
    AnimeStatus,
    AnimeType,
    Country,
    Duration,
    EpisodeId,
    EpisodeNumber,
    ExternalId,
    ExternalIdSource,
    GenreId,
    Language,
    Media,
    MediaKind,
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
    Synopsis,
    TagId,
    Title,
)
from geekbaku.infrastructure.db.models.catalog import (
    AnimeModel,
    EpisodeModel,
    GenreModel,
    ProducerModel,
    SeasonModel,
    StreamingSourceModel,
    StudioModel,
    TagModel,
)

# ---------------------------------------------------------------------------
# Mappers: dominio <-> ORM
# ---------------------------------------------------------------------------


def _media_to_json(media: tuple[Media, ...]) -> list[dict]:
    return [{"kind": str(m.kind), "url": m.url} for m in media]


def _json_to_media(rows: list[dict]) -> list[Media]:
    return [Media(kind=MediaKind(row["kind"]), url=row["url"]) for row in rows]


def _external_ids_to_json(external_ids: tuple[ExternalId, ...]) -> list[dict]:
    return [{"source": str(e.source), "value": e.value} for e in external_ids]


def _json_to_external_ids(rows: list[dict]) -> list[ExternalId]:
    return [
        ExternalId(source=ExternalIdSource(row["source"]), value=row["value"]) for row in rows
    ]


def _relations_to_json(relations: tuple[Relation, ...]) -> list[dict]:
    return [
        {"related_anime_id": str(r.related_anime_id.value), "relation_type": str(r.relation_type)}
        for r in relations
    ]


def _json_to_relations(rows: list[dict]) -> list[Relation]:
    return [
        Relation(
            related_anime_id=AnimeId(uuid.UUID(row["related_anime_id"])),
            relation_type=RelationType(row["relation_type"]),
        )
        for row in rows
    ]


def _streaming_source_to_model(
    source: StreamingSourceEntity, episode_id: uuid.UUID
) -> StreamingSourceModel:
    return StreamingSourceModel(
        id=source.id.value,
        episode_id=episode_id,
        provider_name=source.provider_name,
        external_ref=source.external_ref,
        quality=str(source.quality),
        audio_language_code=source.audio_language.code,
        audio_language_name=source.audio_language.name,
        subtitle_language_code=source.subtitle_language.code if source.subtitle_language else None,
        subtitle_language_name=source.subtitle_language.name if source.subtitle_language else None,
        url=source.url.value if source.url else None,
        is_active=source.is_active,
    )


def _model_to_streaming_source(model: StreamingSourceModel) -> StreamingSourceEntity:
    from geekbaku.domain.catalog.value_objects import VideoUrl

    return StreamingSourceEntity(
        id=StreamingSourceId(model.id),
        provider_name=model.provider_name,
        external_ref=model.external_ref,
        quality=StreamQuality(model.quality),
        audio_language=Language(code=model.audio_language_code, name=model.audio_language_name),
        subtitle_language=(
            Language(code=model.subtitle_language_code, name=model.subtitle_language_name)
            if model.subtitle_language_code
            else None
        ),
        url=VideoUrl(model.url) if model.url else None,
        is_active=model.is_active,
    )


def _episode_to_model(episode: Episode, season_id: uuid.UUID) -> EpisodeModel:
    model = EpisodeModel(
        id=episode.id.value,
        season_id=season_id,
        number=episode.number.value,
        title=str(episode.title),
        synopsis=str(episode.synopsis) if episode.synopsis else None,
        duration_minutes=episode.duration.minutes if episode.duration else None,
        air_date=episode.air_date,
        media=_media_to_json(episode.media),
        external_ids=_external_ids_to_json(episode.external_ids),
    )
    model.streaming_sources = [
        _streaming_source_to_model(source, episode.id.value) for source in episode.streaming_sources
    ]
    return model


def _model_to_episode(model: EpisodeModel) -> Episode:
    episode = Episode(
        id=EpisodeId(model.id),
        number=EpisodeNumber(model.number),
        title=Title(model.title),
        synopsis=Synopsis(model.synopsis) if model.synopsis else None,
        duration=Duration(model.duration_minutes) if model.duration_minutes else None,
        air_date=model.air_date,
    )
    episode._media = _json_to_media(model.media)
    episode._external_ids = _json_to_external_ids(model.external_ids)
    episode._streaming_sources = [_model_to_streaming_source(s) for s in model.streaming_sources]
    return episode


def _season_to_model(season: Season, anime_id: uuid.UUID) -> SeasonModel:
    model = SeasonModel(
        id=season.id.value,
        anime_id=anime_id,
        number=season.number.value,
        title=season.title,
    )
    model.episodes = [_episode_to_model(episode, season.id.value) for episode in season.episodes]
    return model


def _model_to_season(model: SeasonModel) -> Season:
    season = Season(id=SeasonId(model.id), number=SeasonNumber(model.number), title=model.title)
    season._episodes = [_model_to_episode(e) for e in model.episodes]
    return season


def _anime_to_model(anime: Anime) -> AnimeModel:
    model = AnimeModel(
        id=anime.id.value,
        title=str(anime.title),
        slug=str(anime.slug),
        type=str(anime.type),
        status=str(anime.status),
        synopsis=str(anime.synopsis) if anime.synopsis else None,
        country_code=anime.country.code if anime.country else None,
        country_name=anime.country.name if anime.country else None,
        rating_score=anime.rating.score if anime.rating else None,
        rating_votes=anime.rating.votes if anime.rating else None,
        rating_source=anime.rating.source if anime.rating else None,
        genre_ids=[g.value for g in anime.genre_ids],
        studio_ids=[s.value for s in anime.studio_ids],
        producer_ids=[p.value for p in anime.producer_ids],
        tag_ids=[t.value for t in anime.tag_ids],
        media=_media_to_json(anime.media),
        external_ids=_external_ids_to_json(anime.external_ids),
        relations=_relations_to_json(anime.relations),
        created_at=anime.created_at,
        updated_at=anime.updated_at,
    )
    model.seasons = [_season_to_model(season, anime.id.value) for season in anime.seasons]
    return model


def _model_to_anime(model: AnimeModel) -> Anime:
    anime = Anime(
        id=AnimeId(model.id),
        title=Title(model.title),
        slug=Slug(model.slug),
        anime_type=AnimeType(model.type),
        status=AnimeStatus(model.status),
        synopsis=Synopsis(model.synopsis) if model.synopsis else None,
        country=Country(model.country_code, model.country_name)
        if model.country_code and model.country_name
        else None,
        rating=Rating(model.rating_score, model.rating_votes, model.rating_source or "internal")
        if model.rating_score is not None
        else None,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
    anime._genre_ids = {GenreId(v) for v in model.genre_ids}
    anime._studio_ids = {StudioId(v) for v in model.studio_ids}
    anime._producer_ids = {ProducerId(v) for v in model.producer_ids}
    anime._tag_ids = {TagId(v) for v in model.tag_ids}
    anime._media = _json_to_media(model.media)
    anime._external_ids = _json_to_external_ids(model.external_ids)
    anime._relations = _json_to_relations(model.relations)
    anime._seasons = [_model_to_season(s) for s in model.seasons]
    return anime


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------

_ANIME_LOAD_OPTIONS = (
    selectinload(AnimeModel.seasons)
    .selectinload(SeasonModel.episodes)
    .selectinload(EpisodeModel.streaming_sources),
)


class SQLAlchemyAnimeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, anime_id: AnimeId) -> Anime | None:
        stmt = (
            select(AnimeModel).where(AnimeModel.id == anime_id.value).options(*_ANIME_LOAD_OPTIONS)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _model_to_anime(model) if model else None

    async def get_by_slug(self, slug: Slug) -> Anime | None:
        stmt = select(AnimeModel).where(AnimeModel.slug == slug.value).options(*_ANIME_LOAD_OPTIONS)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _model_to_anime(model) if model else None

    async def exists_by_slug(self, slug: Slug) -> bool:
        stmt = select(AnimeModel.id).where(AnimeModel.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list(self, filters: AnimeFilter, pagination: Pagination) -> tuple[list[Anime], int]:
        stmt = select(AnimeModel)

        if filters.status is not None:
            stmt = stmt.where(AnimeModel.status == str(filters.status))
        if filters.type is not None:
            stmt = stmt.where(AnimeModel.type == str(filters.type))
        if filters.country_code is not None:
            stmt = stmt.where(AnimeModel.country_code == filters.country_code)
        if filters.genre_id is not None:
            stmt = stmt.where(AnimeModel.genre_ids.any(filters.genre_id.value))
        if filters.studio_id is not None:
            stmt = stmt.where(AnimeModel.studio_ids.any(filters.studio_id.value))
        if filters.producer_id is not None:
            stmt = stmt.where(AnimeModel.producer_ids.any(filters.producer_id.value))
        if filters.tag_id is not None:
            stmt = stmt.where(AnimeModel.tag_ids.any(filters.tag_id.value))
        if filters.search_text is not None:
            stmt = stmt.where(AnimeModel.title.ilike(f"%{filters.search_text}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.options(*_ANIME_LOAD_OPTIONS)
            .order_by(AnimeModel.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_model_to_anime(m) for m in models], total

    async def add(self, anime: Anime) -> None:
        self._session.add(_anime_to_model(anime))
        await self._session.flush()

    async def update(self, anime: Anime) -> None:
        stmt = (
            select(AnimeModel)
            .where(AnimeModel.id == anime.id.value)
            .options(*_ANIME_LOAD_OPTIONS)
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            await self._session.delete(existing)
            await self._session.flush()
        self._session.add(_anime_to_model(anime))
        await self._session.flush()


class SQLAlchemyEpisodeRepository:
    """Consulta episodios directamente, sin pasar por el agregado `Anime`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, episode_id: EpisodeId) -> Episode | None:
        stmt = (
            select(EpisodeModel)
            .where(EpisodeModel.id == episode_id.value)
            .options(selectinload(EpisodeModel.streaming_sources))
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _model_to_episode(model) if model else None


class SQLAlchemyGenreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, genre_id: GenreId) -> Genre | None:
        model = await self._session.get(GenreModel, genre_id.value)
        return Genre(GenreId(model.id), model.name, Slug(model.slug)) if model else None

    async def get_by_slug(self, slug: Slug) -> Genre | None:
        stmt = select(GenreModel).where(GenreModel.slug == slug.value)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return Genre(GenreId(model.id), model.name, Slug(model.slug)) if model else None

    async def get_many_by_ids(self, genre_ids: set[GenreId]) -> list[Genre]:
        stmt = select(GenreModel).where(GenreModel.id.in_([g.value for g in genre_ids]))
        models = (await self._session.execute(stmt)).scalars().all()
        return [Genre(GenreId(m.id), m.name, Slug(m.slug)) for m in models]

    async def exists_by_slug(self, slug: Slug) -> bool:
        stmt = select(GenreModel.id).where(GenreModel.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list_all(self) -> list[Genre]:
        models = (await self._session.execute(select(GenreModel))).scalars().all()
        return [Genre(GenreId(m.id), m.name, Slug(m.slug)) for m in models]

    async def add(self, genre: Genre) -> None:
        self._session.add(GenreModel(id=genre.id.value, name=genre.name, slug=str(genre.slug)))
        await self._session.flush()


class SQLAlchemyStudioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: StudioModel) -> Studio:
        country = (
            Country(model.country_code, model.country_name)
            if model.country_code and model.country_name
            else None
        )
        return Studio(StudioId(model.id), model.name, Slug(model.slug), country)

    async def get_by_id(self, studio_id: StudioId) -> Studio | None:
        model = await self._session.get(StudioModel, studio_id.value)
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: Slug) -> Studio | None:
        stmt = select(StudioModel).where(StudioModel.slug == slug.value)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_many_by_ids(self, studio_ids: set[StudioId]) -> list[Studio]:
        stmt = select(StudioModel).where(StudioModel.id.in_([s.value for s in studio_ids]))
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in models]

    async def exists_by_slug(self, slug: Slug) -> bool:
        stmt = select(StudioModel.id).where(StudioModel.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list_all(self) -> list[Studio]:
        models = (await self._session.execute(select(StudioModel))).scalars().all()
        return [self._to_entity(m) for m in models]

    async def add(self, studio: Studio) -> None:
        self._session.add(
            StudioModel(
                id=studio.id.value,
                name=studio.name,
                slug=str(studio.slug),
                country_code=studio.country.code if studio.country else None,
                country_name=studio.country.name if studio.country else None,
            )
        )
        await self._session.flush()


class SQLAlchemyProducerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: ProducerModel) -> Producer:
        country = (
            Country(model.country_code, model.country_name)
            if model.country_code and model.country_name
            else None
        )
        return Producer(ProducerId(model.id), model.name, Slug(model.slug), country)

    async def get_by_id(self, producer_id: ProducerId) -> Producer | None:
        model = await self._session.get(ProducerModel, producer_id.value)
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: Slug) -> Producer | None:
        stmt = select(ProducerModel).where(ProducerModel.slug == slug.value)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_many_by_ids(self, producer_ids: set[ProducerId]) -> list[Producer]:
        stmt = select(ProducerModel).where(ProducerModel.id.in_([p.value for p in producer_ids]))
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in models]

    async def exists_by_slug(self, slug: Slug) -> bool:
        stmt = select(ProducerModel.id).where(ProducerModel.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list_all(self) -> list[Producer]:
        models = (await self._session.execute(select(ProducerModel))).scalars().all()
        return [self._to_entity(m) for m in models]

    async def add(self, producer: Producer) -> None:
        self._session.add(
            ProducerModel(
                id=producer.id.value,
                name=producer.name,
                slug=str(producer.slug),
                country_code=producer.country.code if producer.country else None,
                country_name=producer.country.name if producer.country else None,
            )
        )
        await self._session.flush()


class SQLAlchemyTagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tag_id: TagId) -> Tag | None:
        model = await self._session.get(TagModel, tag_id.value)
        return Tag(TagId(model.id), model.name, Slug(model.slug)) if model else None

    async def get_by_slug(self, slug: Slug) -> Tag | None:
        stmt = select(TagModel).where(TagModel.slug == slug.value)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return Tag(TagId(model.id), model.name, Slug(model.slug)) if model else None

    async def get_many_by_ids(self, tag_ids: set[TagId]) -> list[Tag]:
        stmt = select(TagModel).where(TagModel.id.in_([t.value for t in tag_ids]))
        models = (await self._session.execute(stmt)).scalars().all()
        return [Tag(TagId(m.id), m.name, Slug(m.slug)) for m in models]

    async def exists_by_slug(self, slug: Slug) -> bool:
        stmt = select(TagModel.id).where(TagModel.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list_all(self) -> list[Tag]:
        models = (await self._session.execute(select(TagModel))).scalars().all()
        return [Tag(TagId(m.id), m.name, Slug(m.slug)) for m in models]

    async def add(self, tag: Tag) -> None:
        self._session.add(TagModel(id=tag.id.value, name=tag.name, slug=str(tag.slug)))
        await self._session.flush()


class SQLAlchemyCatalogUnitOfWork:
    """Una `AsyncSession` por unit of work: `commit`/`rollback` delegan
    directamente en la transacción real de Postgres.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.animes: AnimeRepository = SQLAlchemyAnimeRepository(session)
        self.episodes: EpisodeRepository = SQLAlchemyEpisodeRepository(session)
        self.genres: GenreRepository = SQLAlchemyGenreRepository(session)
        self.studios: StudioRepository = SQLAlchemyStudioRepository(session)
        self.producers: ProducerRepository = SQLAlchemyProducerRepository(session)
        self.tags: TagRepository = SQLAlchemyTagRepository(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


__all__ = ["SQLAlchemyCatalogUnitOfWork"]
