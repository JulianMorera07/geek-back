"""Entidades del módulo de catálogo.

- `Genre`, `Studio`, `Producer`, `Tag` son Aggregate Roots simples (catálogos
  abiertos, cada uno con su propio repositorio).
- `Anime` es el Aggregate Root principal. `Season` y `Episode` son entidades
  hijas, solo accesibles/mutables a través de `Anime` (y `Season` para
  `Episode`), lo que mantiene las invariantes (numeración única, etc.)
  dentro del límite del agregado.
- `StreamingSource` es una entidad hija de `Episode`.

Todas las entidades comparan igualdad e implementan `__hash__` en base a su
identidad (`id`), como corresponde a una Entity en DDD (a diferencia de los
Value Objects, que comparan por valor).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from geekbaku.domain.catalog.exceptions import (
    DuplicateEpisodeNumberError,
    DuplicateExternalIdError,
    DuplicateRelationError,
    DuplicateSeasonNumberError,
    DuplicateStreamingSourceError,
    EpisodeNotFoundError,
    InvalidStatusTransitionError,
    SeasonNotFoundError,
    SelfRelationError,
    StreamingSourceNotFoundError,
)
from geekbaku.domain.catalog.value_objects import (
    AnimeId,
    AnimeStatus,
    AnimeType,
    Banner,
    Country,
    Duration,
    EpisodeId,
    EpisodeNumber,
    ExternalId,
    GenreId,
    ImageUrl,
    Language,
    Media,
    MediaKind,
    ProducerId,
    Rating,
    Relation,
    SeasonId,
    SeasonNumber,
    Slug,
    StreamingSourceId,
    StreamQuality,
    StudioId,
    Synopsis,
    TagId,
    Thumbnail,
    Title,
    Trailer,
    VideoUrl,
)
from geekbaku.domain.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Catálogos abiertos (Aggregate Roots simples)
# ---------------------------------------------------------------------------


class Genre:
    """Género narrativo/temático (ej. 'Shonen', 'Isekai')."""

    def __init__(self, id: GenreId, name: str, slug: Slug) -> None:
        if not name.strip():
            raise ValidationError("El nombre del género no puede estar vacío.")
        self.id = id
        self.name = name
        self.slug = slug

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Genre) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Studio:
    """Estudio de animación responsable de producir un Anime."""

    def __init__(
        self,
        id: StudioId,
        name: str,
        slug: Slug,
        country: Country | None = None,
    ) -> None:
        if not name.strip():
            raise ValidationError("El nombre del estudio no puede estar vacío.")
        self.id = id
        self.name = name
        self.slug = slug
        self.country = country

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Studio) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Producer:
    """Compañía productora/patrocinadora de un Anime.

    Distinta de `Studio`: el `Studio` es quien anima la obra, el `Producer`
    es la empresa (comité de producción, licenciante, etc.) que la financia
    o distribuye. Un Anime puede tener varios de cada uno.
    """

    def __init__(
        self,
        id: ProducerId,
        name: str,
        slug: Slug,
        country: Country | None = None,
    ) -> None:
        if not name.strip():
            raise ValidationError("El nombre del productor no puede estar vacío.")
        self.id = id
        self.name = name
        self.slug = slug
        self.country = country

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Producer) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Tag:
    """Etiqueta libre de catálogo (ej. 'time-travel', 'tournament-arc')."""

    def __init__(self, id: TagId, name: str, slug: Slug) -> None:
        if not name.strip():
            raise ValidationError("El nombre del tag no puede estar vacío.")
        self.id = id
        self.name = name
        self.slug = slug

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tag) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ---------------------------------------------------------------------------
# Streaming source (entidad hija de Episode)
# ---------------------------------------------------------------------------


class StreamingSource:
    """Referencia a dónde y en qué calidad/idioma se puede reproducir un Episode.

    `provider_name`/`external_ref` identifican el contenido en un proveedor
    externo; la resolución de la URL real de reproducción (que puede expirar)
    es responsabilidad de la capa de providers, fuera del alcance de este
    sprint. `url` aquí es opcional y representa un enlace ya conocido/persistido
    (ej. embebido propio), no el resultado de una resolución dinámica.
    """

    def __init__(
        self,
        id: StreamingSourceId,
        provider_name: str,
        external_ref: str,
        quality: StreamQuality,
        audio_language: Language,
        subtitle_language: Language | None = None,
        url: VideoUrl | None = None,
        is_active: bool = True,
    ) -> None:
        if not provider_name.strip():
            raise ValidationError("El provider_name no puede estar vacío.")
        if not external_ref.strip():
            raise ValidationError("El external_ref no puede estar vacío.")
        self.id = id
        self.provider_name = provider_name
        self.external_ref = external_ref
        self.quality = quality
        self.audio_language = audio_language
        self.subtitle_language = subtitle_language
        self.url = url
        self.is_active = is_active

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StreamingSource) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ---------------------------------------------------------------------------
# Episode / Season (entidades hijas de Anime)
# ---------------------------------------------------------------------------


class Episode:
    """Episodio reproducible, hijo de una Season."""

    def __init__(
        self,
        id: EpisodeId,
        number: EpisodeNumber,
        title: Title,
        synopsis: Synopsis | None = None,
        duration: Duration | None = None,
        air_date: date | None = None,
    ) -> None:
        self.id = id
        self.number = number
        self.title = title
        self.synopsis = synopsis
        self.duration = duration
        self.air_date = air_date
        self._media: list[Media] = []
        self._external_ids: list[ExternalId] = []
        self._streaming_sources: list[StreamingSource] = []

    @property
    def media(self) -> tuple[Media, ...]:
        return tuple(self._media)

    @property
    def external_ids(self) -> tuple[ExternalId, ...]:
        return tuple(self._external_ids)

    @property
    def streaming_sources(self) -> tuple[StreamingSource, ...]:
        return tuple(self._streaming_sources)

    @property
    def thumbnail(self) -> Thumbnail | None:
        for item in self._media:
            if item.kind == MediaKind.THUMBNAIL:
                return Thumbnail(ImageUrl(item.url))
        return None

    def add_media(self, media: Media) -> None:
        self._media.append(media)

    def add_external_id(self, external_id: ExternalId) -> None:
        if any(existing.source == external_id.source for existing in self._external_ids):
            raise DuplicateExternalIdError(
                f"El episodio {self.id} ya tiene un external id de la fuente "
                f"'{external_id.source}'."
            )
        self._external_ids.append(external_id)

    def add_streaming_source(self, source: StreamingSource) -> None:
        duplicate = any(
            existing.provider_name == source.provider_name
            and existing.external_ref == source.external_ref
            for existing in self._streaming_sources
        )
        if duplicate:
            raise DuplicateStreamingSourceError(
                f"El episodio {self.id} ya tiene una fuente de "
                f"'{source.provider_name}' con external_ref '{source.external_ref}'."
            )
        self._streaming_sources.append(source)

    def remove_streaming_source(self, streaming_source_id: StreamingSourceId) -> None:
        for existing in self._streaming_sources:
            if existing.id == streaming_source_id:
                self._streaming_sources.remove(existing)
                return
        raise StreamingSourceNotFoundError(
            f"El episodio {self.id} no tiene una fuente con id {streaming_source_id}."
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Episode) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Season:
    """Temporada de un Anime, agrupa Episodes."""

    def __init__(self, id: SeasonId, number: SeasonNumber, title: str | None = None) -> None:
        self.id = id
        self.number = number
        self.title = title
        self._episodes: list[Episode] = []

    @property
    def episodes(self) -> tuple[Episode, ...]:
        return tuple(self._episodes)

    def add_episode(self, episode: Episode) -> None:
        if any(existing.number == episode.number for existing in self._episodes):
            raise DuplicateEpisodeNumberError(
                f"La temporada {self.id} ya tiene un episodio número {episode.number}."
            )
        self._episodes.append(episode)

    def get_episode(self, episode_id: EpisodeId) -> Episode:
        for episode in self._episodes:
            if episode.id == episode_id:
                return episode
        raise EpisodeNotFoundError(
            f"No existe el episodio {episode_id} en la temporada {self.id}."
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Season) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# ---------------------------------------------------------------------------
# Anime (Aggregate Root)
# ---------------------------------------------------------------------------

#: Transiciones de AnimeStatus permitidas. Un estado no listado como origen
#: (COMPLETED, CANCELLED) es terminal.
_ALLOWED_STATUS_TRANSITIONS: dict[AnimeStatus, frozenset[AnimeStatus]] = {
    AnimeStatus.ANNOUNCED: frozenset({AnimeStatus.ONGOING, AnimeStatus.CANCELLED}),
    AnimeStatus.ONGOING: frozenset(
        {AnimeStatus.PAUSED, AnimeStatus.COMPLETED, AnimeStatus.CANCELLED}
    ),
    AnimeStatus.PAUSED: frozenset({AnimeStatus.ONGOING, AnimeStatus.CANCELLED}),
    AnimeStatus.COMPLETED: frozenset(),
    AnimeStatus.CANCELLED: frozenset(),
}


class Anime:
    """Aggregate Root del catálogo.

    Encapsula `Season`/`Episode` (entidades hijas, dentro del límite de este
    agregado) y referencias por id a `Genre`/`Studio`/`Tag` (agregados
    independientes, resueltos por la capa de aplicación cuando haga falta
    mostrar sus datos).
    """

    def __init__(
        self,
        id: AnimeId,
        title: Title,
        slug: Slug,
        anime_type: AnimeType,
        status: AnimeStatus = AnimeStatus.ANNOUNCED,
        synopsis: Synopsis | None = None,
        country: Country | None = None,
        rating: Rating | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.title = title
        self.slug = slug
        self.type = anime_type
        self.status = status
        self.synopsis = synopsis
        self.country = country
        self.rating = rating
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or self.created_at

        self._genre_ids: set[GenreId] = set()
        self._studio_ids: set[StudioId] = set()
        self._producer_ids: set[ProducerId] = set()
        self._tag_ids: set[TagId] = set()
        self._media: list[Media] = []
        self._external_ids: list[ExternalId] = []
        self._relations: list[Relation] = []
        self._seasons: list[Season] = []

    # -- vistas de solo lectura -------------------------------------------------

    @property
    def genre_ids(self) -> frozenset[GenreId]:
        return frozenset(self._genre_ids)

    @property
    def studio_ids(self) -> frozenset[StudioId]:
        return frozenset(self._studio_ids)

    @property
    def producer_ids(self) -> frozenset[ProducerId]:
        return frozenset(self._producer_ids)

    @property
    def tag_ids(self) -> frozenset[TagId]:
        return frozenset(self._tag_ids)

    @property
    def media(self) -> tuple[Media, ...]:
        return tuple(self._media)

    @property
    def thumbnail(self) -> Thumbnail | None:
        for item in self._media:
            if item.kind == MediaKind.THUMBNAIL:
                return Thumbnail(ImageUrl(item.url))
        return None

    @property
    def banner(self) -> Banner | None:
        for item in self._media:
            if item.kind == MediaKind.BANNER:
                return Banner(ImageUrl(item.url))
        return None

    @property
    def trailer(self) -> Trailer | None:
        for item in self._media:
            if item.kind == MediaKind.TRAILER:
                return Trailer(VideoUrl(item.url))
        return None

    @property
    def external_ids(self) -> tuple[ExternalId, ...]:
        return tuple(self._external_ids)

    @property
    def relations(self) -> tuple[Relation, ...]:
        return tuple(self._relations)

    @property
    def seasons(self) -> tuple[Season, ...]:
        return tuple(self._seasons)

    # -- mutadores que preservan invariantes ------------------------------------

    def add_genre(self, genre_id: GenreId) -> None:
        self._genre_ids.add(genre_id)
        self._touch()

    def add_studio(self, studio_id: StudioId) -> None:
        self._studio_ids.add(studio_id)
        self._touch()

    def add_producer(self, producer_id: ProducerId) -> None:
        self._producer_ids.add(producer_id)
        self._touch()

    def add_tag(self, tag_id: TagId) -> None:
        self._tag_ids.add(tag_id)
        self._touch()

    def add_media(self, media: Media) -> None:
        self._media.append(media)
        self._touch()

    def set_rating(self, rating: Rating) -> None:
        self.rating = rating
        self._touch()

    def add_external_id(self, external_id: ExternalId) -> None:
        if any(existing.source == external_id.source for existing in self._external_ids):
            raise DuplicateExternalIdError(
                f"El anime {self.id} ya tiene un external id de la fuente "
                f"'{external_id.source}'."
            )
        self._external_ids.append(external_id)
        self._touch()

    def add_relation(self, relation: Relation) -> None:
        if relation.related_anime_id == self.id:
            raise SelfRelationError(f"El anime {self.id} no puede relacionarse consigo mismo.")
        duplicate = any(
            existing.related_anime_id == relation.related_anime_id
            and existing.relation_type == relation.relation_type
            for existing in self._relations
        )
        if duplicate:
            raise DuplicateRelationError(
                f"El anime {self.id} ya tiene una relación "
                f"'{relation.relation_type}' hacia {relation.related_anime_id}."
            )
        self._relations.append(relation)
        self._touch()

    def add_season(self, season: Season) -> None:
        if any(existing.number == season.number for existing in self._seasons):
            raise DuplicateSeasonNumberError(
                f"El anime {self.id} ya tiene una temporada número {season.number}."
            )
        self._seasons.append(season)
        self._touch()

    def get_season(self, season_id: SeasonId) -> Season:
        for season in self._seasons:
            if season.id == season_id:
                return season
        raise SeasonNotFoundError(f"No existe la temporada {season_id} en el anime {self.id}.")

    def find_episode(self, episode_id: EpisodeId) -> Episode:
        """Busca un Episode en cualquiera de las Seasons del Anime."""
        for season in self._seasons:
            for episode in season.episodes:
                if episode.id == episode_id:
                    return episode
        raise EpisodeNotFoundError(f"No existe el episodio {episode_id} en el anime {self.id}.")

    def change_status(self, new_status: AnimeStatus) -> None:
        if new_status == self.status:
            return
        allowed = _ALLOWED_STATUS_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                f"No se puede pasar de estado '{self.status}' a '{new_status}'."
            )
        self.status = new_status
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Anime) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
