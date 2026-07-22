"""Value Objects del módulo de reproducción (Playback Engine).

Reutiliza vocabulario ya establecido en `domain.catalog` (`StreamQuality`,
`Language`, `VideoUrl`) en vez de duplicarlo: la calidad de video y el
idioma de un audio/subtítulo de reproducción son el mismo concepto que ya
existe para `catalog.StreamingSource`, no algo nuevo. La dependencia es en
un solo sentido (`playback` -> `catalog`), igual que `providers` -> `catalog`.

Sin autenticación todavía: una `PlaybackSession` es anónima (no tiene
`user_id`), identificada solo por su propio id. Guardar/leer progreso no
requiere saber "de quién" es, solo "de qué sesión" — la asociación con un
usuario real es un enlace que un sprint futuro (con auth) puede agregar sin
romper este modelo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from geekbaku.domain.catalog.value_objects import Language
from geekbaku.domain.shared.errors import ValidationError

_URL_PATTERN = re.compile(r"^https?://.+", re.IGNORECASE)


def _new_uuid() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Identidades tipadas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlaybackSessionId:
    value: UUID

    @staticmethod
    def new() -> PlaybackSessionId:
        return PlaybackSessionId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class PlaybackSourceId:
    value: UUID

    @staticmethod
    def new() -> PlaybackSourceId:
        return PlaybackSourceId(_new_uuid())

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Enumeraciones cerradas
# ---------------------------------------------------------------------------


class PlaybackSessionStatus(StrEnum):
    """Estado de una sesión de reproducción."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SubtitleFormat(StrEnum):
    VTT = "vtt"
    SRT = "srt"
    ASS = "ass"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SubtitleUrl:
    """URL http(s) de un archivo de subtítulos."""

    value: str

    def __post_init__(self) -> None:
        if not _URL_PATTERN.match(self.value):
            raise ValidationError(f"'{self.value}' no es una URL http(s) válida.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Subtitle:
    """Pista de subtítulos disponible para un `PlaybackSource`.

    `url` es opcional: `None` significa que el subtítulo está "hardsub"
    (grabado en el video de ese `PlaybackSource`, común en releases de
    fansub de un solo archivo) — en ese caso, "elegir" este idioma implica
    elegir esa fuente específica, no cargar un archivo aparte. Con `url`
    presente, es un softsub real, seleccionable independientemente de la
    fuente de video.
    """

    language: Language
    format: SubtitleFormat
    url: SubtitleUrl | None = None
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class AudioTrack:
    """Pista de audio disponible para un `PlaybackSource`."""

    language: Language
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class StreamingServer:
    """Servidor/CDN concreto que sirve un `PlaybackSource`.

    Distinto de `PlaybackProvider`: un mismo provider puede servir el mismo
    contenido desde varios servidores espejo (ej. "server1", "server2"), y
    el `SourceResolver` puede necesitar elegir entre ellos igual que entre
    calidades.
    """

    name: str
    base_url: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("El nombre del StreamingServer no puede estar vacío.")
        if not _URL_PATTERN.match(self.base_url):
            raise ValidationError(f"'{self.base_url}' no es una URL http(s) válida.")


@dataclass(frozen=True, slots=True)
class PlaybackProvider:
    """Identifica qué provider (del Provider Framework) sirvió un
    `PlaybackSource`, con la prioridad que el `SourceResolver` usa para
    ordenar entre fuentes de distintos providers.

    Es deliberadamente una identidad liviana (no importa
    `domain.providers.ProviderId` ni ningún tipo del Provider Framework):
    el Playback Engine debe poder describir de dónde vino una fuente sin
    acoplarse a la implementación de cómo se obtuvo.
    """

    provider_id: str
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValidationError("El provider_id no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class PlaybackMetadata:
    """Información de despliegue para el reproductor (UI), ya normalizada
    (viene del catálogo interno, nunca directo de un provider).
    """

    title: str
    anime_title: str
    season_number: int
    episode_number: int
    duration_seconds: int | None = None
    thumbnail_url: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("El título no puede estar vacío.")
        if self.season_number <= 0:
            raise ValidationError("season_number debe ser mayor a 0.")
        if self.episode_number <= 0:
            raise ValidationError("episode_number debe ser mayor a 0.")
        if self.duration_seconds is not None and self.duration_seconds <= 0:
            raise ValidationError("duration_seconds debe ser mayor a 0.")


@dataclass(frozen=True, slots=True)
class WatchProgress:
    """Progreso de reproducción en un momento dado, dentro de una sesión."""

    position_seconds: int
    duration_seconds: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.position_seconds < 0:
            raise ValidationError("position_seconds no puede ser negativo.")
        if self.duration_seconds <= 0:
            raise ValidationError("duration_seconds debe ser mayor a 0.")
        if self.position_seconds > self.duration_seconds:
            raise ValidationError("position_seconds no puede superar duration_seconds.")

    @property
    def percentage(self) -> float:
        return (self.position_seconds / self.duration_seconds) * 100.0

    @staticmethod
    def at(position_seconds: int, duration_seconds: int) -> WatchProgress:
        return WatchProgress(
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class ResumePoint:
    """Punto desde donde debería reanudarse la reproducción.

    No es simplemente "la última posición guardada": `ResumePointService`
    aplica la regla de negocio de reiniciar desde 0 cuando el progreso está
    cerca del final (evita reanudar 3 segundos antes de que termine un
    episodio ya visto) o al principio (evita "reanudar" un progreso
    insignificante).
    """

    position_seconds: int
    is_completed: bool

    def __post_init__(self) -> None:
        if self.position_seconds < 0:
            raise ValidationError("position_seconds no puede ser negativo.")


__all__ = [
    "AudioTrack",
    "PlaybackMetadata",
    "PlaybackProvider",
    "PlaybackSessionId",
    "PlaybackSessionStatus",
    "PlaybackSourceId",
    "ResumePoint",
    "StreamingServer",
    "Subtitle",
    "SubtitleFormat",
    "SubtitleUrl",
    "WatchProgress",
]
