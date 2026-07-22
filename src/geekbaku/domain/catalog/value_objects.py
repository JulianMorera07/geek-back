"""Value Objects del módulo de catálogo.

Todos los VOs son inmutables (`frozen=True`) y se auto-validan en `__post_init__`.
Ninguno depende de SQLAlchemy, Pydantic ni FastAPI: son Python puro, para que el
dominio siga siendo importable sin ningún framework instalado.

Decisión de modelado (ver docs/architecture.md):
- `Country` y `Language` son datos de referencia basados en estándares ISO
  (3166-1 alpha-2 y 639-1 respectivamente). Se validan por formato, no se
  gestionan como agregados con repositorio propio: no tiene sentido de
  negocio "crear" un país o idioma nuevo desde la aplicación.
- `AnimeType` y `AnimeStatus` son enumeraciones cerradas: el conjunto de
  valores posibles es una decisión de negocio estable, no un catálogo abierto.
- `Genre`, `Studio` y `Tag`, en cambio, son catálogos abiertos que el negocio
  necesita poder crear/gestionar dinámicamente, por eso se modelan como
  entidades con identidad propia en `entities.py`, con su propio repositorio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from geekbaku.domain.shared.errors import ValidationError

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ISO_COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
_ISO_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}$")
_URL_PATTERN = re.compile(r"^https?://.+", re.IGNORECASE)


def _new_uuid() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Identidades tipadas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnimeId:
    value: UUID

    @staticmethod
    def new() -> AnimeId:
        return AnimeId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SeasonId:
    value: UUID

    @staticmethod
    def new() -> SeasonId:
        return SeasonId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class EpisodeId:
    value: UUID

    @staticmethod
    def new() -> EpisodeId:
        return EpisodeId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class GenreId:
    value: UUID

    @staticmethod
    def new() -> GenreId:
        return GenreId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class StudioId:
    value: UUID

    @staticmethod
    def new() -> StudioId:
        return StudioId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TagId:
    value: UUID

    @staticmethod
    def new() -> TagId:
        return TagId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class StreamingSourceId:
    value: UUID

    @staticmethod
    def new() -> StreamingSourceId:
        return StreamingSourceId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ProducerId:
    value: UUID

    @staticmethod
    def new() -> ProducerId:
        return ProducerId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Texto / identificadores legibles
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Slug:
    """Identificador legible y único usado en URLs (ej. 'attack-on-titan')."""

    value: str

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.match(self.value):
            raise ValidationError(
                f"'{self.value}' no es un slug válido "
                "(debe ser kebab-case: minúsculas, dígitos y guiones)."
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Title:
    """Título de un Anime o Episode. No puede estar vacío."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValidationError("El título no puede estar vacío.")
        if len(self.value) > 255:
            raise ValidationError("El título no puede superar 255 caracteres.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Synopsis:
    """Sinopsis opcional de un Anime o Episode."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > 5000:
            raise ValidationError("La sinopsis no puede superar 5000 caracteres.")

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Enumeraciones cerradas
# ---------------------------------------------------------------------------


class AnimeType(StrEnum):
    """Formato de producción del anime."""

    TV = "tv"
    MOVIE = "movie"
    OVA = "ova"
    ONA = "ona"
    SPECIAL = "special"
    MUSIC = "music"


class AnimeStatus(StrEnum):
    """Estado de emisión/producción de un Anime."""

    ANNOUNCED = "announced"
    ONGOING = "ongoing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MediaKind(StrEnum):
    """Tipo de recurso visual asociado a un Anime o Episode."""

    COVER = "cover"
    BANNER = "banner"
    LOGO = "logo"
    TRAILER = "trailer"
    THUMBNAIL = "thumbnail"


class ExternalIdSource(StrEnum):
    """Catálogos externos de referencia (metadata), no proveedores de video."""

    MAL = "mal"
    ANILIST = "anilist"
    TMDB = "tmdb"
    IMDB = "imdb"
    TVDB = "tvdb"
    KITSU = "kitsu"
    OTHER = "other"


class RelationType(StrEnum):
    """Tipo de relación narrativa entre dos Anime."""

    SEQUEL = "sequel"
    PREQUEL = "prequel"
    SIDE_STORY = "side_story"
    PARENT_STORY = "parent_story"
    SPIN_OFF = "spin_off"
    ALTERNATIVE_VERSION = "alternative_version"
    ADAPTATION = "adaptation"
    SUMMARY = "summary"
    OTHER = "other"


#: Inversa narrativa de cada RelationType, usada por `RelationLinkingService`
#: para mantener la relación consistente en ambos Anime (ej. si A es SEQUEL
#: de B, entonces B es PREQUEL de A).
RELATION_INVERSE: dict[RelationType, RelationType] = {
    RelationType.SEQUEL: RelationType.PREQUEL,
    RelationType.PREQUEL: RelationType.SEQUEL,
    RelationType.SIDE_STORY: RelationType.PARENT_STORY,
    RelationType.PARENT_STORY: RelationType.SIDE_STORY,
    RelationType.SPIN_OFF: RelationType.PARENT_STORY,
    RelationType.ALTERNATIVE_VERSION: RelationType.ALTERNATIVE_VERSION,
    RelationType.ADAPTATION: RelationType.ADAPTATION,
    RelationType.SUMMARY: RelationType.PARENT_STORY,
    RelationType.OTHER: RelationType.OTHER,
}


class StreamQuality(StrEnum):
    """Calidad de video de una fuente de streaming."""

    SD = "sd"
    HD = "hd"
    FHD = "fhd"
    UHD = "uhd"


#: Orden de preferencia (menor a mayor calidad), usado por
#: `EpisodeAvailabilityService` para elegir la mejor fuente disponible.
STREAM_QUALITY_RANK: dict[StreamQuality, int] = {
    StreamQuality.SD: 0,
    StreamQuality.HD: 1,
    StreamQuality.FHD: 2,
    StreamQuality.UHD: 3,
}


# ---------------------------------------------------------------------------
# Datos de referencia (ISO)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Country:
    """País de origen, identificado por código ISO 3166-1 alpha-2."""

    code: str
    name: str

    def __post_init__(self) -> None:
        if not _ISO_COUNTRY_PATTERN.match(self.code):
            raise ValidationError(
                f"'{self.code}' no es un código de país ISO 3166-1 alpha-2 válido."
            )
        if not self.name.strip():
            raise ValidationError("El nombre del país no puede estar vacío.")

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class Language:
    """Idioma, identificado por código ISO 639-1."""

    code: str
    name: str

    def __post_init__(self) -> None:
        if not _ISO_LANGUAGE_PATTERN.match(self.code):
            raise ValidationError(f"'{self.code}' no es un código de idioma ISO 639-1 válido.")
        if not self.name.strip():
            raise ValidationError("El nombre del idioma no puede estar vacío.")

    def __str__(self) -> str:
        return self.code


# ---------------------------------------------------------------------------
# Numeración
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeasonNumber:
    """Número de temporada dentro de un Anime (1-indexed)."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError("El número de temporada debe ser mayor a 0.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class EpisodeNumber:
    """Número de episodio dentro de una Season (1-indexed)."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError("El número de episodio debe ser mayor a 0.")

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Otros Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Duration:
    """Duración en minutos de un episodio."""

    minutes: int

    def __post_init__(self) -> None:
        if self.minutes <= 0:
            raise ValidationError("La duración debe ser mayor a 0 minutos.")
        if self.minutes > 600:
            raise ValidationError("La duración no puede superar 600 minutos.")


@dataclass(frozen=True, slots=True)
class ImageUrl:
    """URL http(s) que apunta a un recurso de imagen."""

    value: str

    def __post_init__(self) -> None:
        if not _URL_PATTERN.match(self.value):
            raise ValidationError(f"'{self.value}' no es una URL http(s) válida.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class VideoUrl:
    """URL http(s) que apunta a un recurso de video."""

    value: str

    def __post_init__(self) -> None:
        if not _URL_PATTERN.match(self.value):
            raise ValidationError(f"'{self.value}' no es una URL http(s) válida.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Thumbnail:
    """Imagen de miniatura de un Anime o Episode."""

    url: ImageUrl


@dataclass(frozen=True, slots=True)
class Banner:
    """Imagen de cabecera/banner de un Anime."""

    url: ImageUrl


@dataclass(frozen=True, slots=True)
class Trailer:
    """Video promocional de un Anime."""

    url: VideoUrl


@dataclass(frozen=True, slots=True)
class Rating:
    """Puntuación agregada de un Anime.

    `source` identifica el origen de la puntuación (ej. 'internal', 'mal',
    'anilist'): GeekBaku puede combinar su propio rating con el de catálogos
    externos, cada uno representado por una instancia distinta.
    """

    score: float
    votes: int | None = None
    source: str = "internal"

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 10.0):
            raise ValidationError("El score de un Rating debe estar entre 0.0 y 10.0.")
        if self.votes is not None and self.votes < 0:
            raise ValidationError("El número de votos no puede ser negativo.")
        if not self.source.strip():
            raise ValidationError("El source de un Rating no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class Media:
    """Recurso visual (imagen o video) asociado a un Anime o Episode."""

    kind: MediaKind
    url: str

    def __post_init__(self) -> None:
        if not _URL_PATTERN.match(self.url):
            raise ValidationError(f"'{self.url}' no es una URL http(s) válida.")


@dataclass(frozen=True, slots=True)
class ExternalId:
    """Identificador del Anime/Episode en un catálogo externo de referencia."""

    source: ExternalIdSource
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValidationError("El valor del external id no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class Relation:
    """Relación narrativa dirigida hacia otro Anime."""

    related_anime_id: AnimeId
    relation_type: RelationType


@dataclass(frozen=True, slots=True)
class AnimeFilter:
    """Criterios de filtrado para listar el catálogo (`AnimeRepository.list`)."""

    status: AnimeStatus | None = None
    type: AnimeType | None = None
    country_code: str | None = None
    genre_id: GenreId | None = None
    studio_id: StudioId | None = None
    producer_id: ProducerId | None = None
    tag_id: TagId | None = None
    search_text: str | None = None


__all__ = [
    "RELATION_INVERSE",
    "STREAM_QUALITY_RANK",
    "AnimeFilter",
    "AnimeId",
    "AnimeStatus",
    "AnimeType",
    "Banner",
    "Country",
    "Duration",
    "EpisodeId",
    "EpisodeNumber",
    "ExternalId",
    "ExternalIdSource",
    "GenreId",
    "ImageUrl",
    "Language",
    "Media",
    "MediaKind",
    "ProducerId",
    "Rating",
    "Relation",
    "RelationType",
    "SeasonId",
    "SeasonNumber",
    "Slug",
    "StreamQuality",
    "StreamingSourceId",
    "StudioId",
    "Synopsis",
    "TagId",
    "Thumbnail",
    "Title",
    "Trailer",
    "VideoUrl",
]
