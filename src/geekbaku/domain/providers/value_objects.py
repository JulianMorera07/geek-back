"""Value Objects del módulo de providers (motor de proveedores externos).

Este módulo modela el vocabulario de dominio para integrar múltiples fuentes
externas de contenido (streaming providers) detrás de una única interfaz
(`application/providers/ports.py:ProviderPort`). Depende de
`geekbaku.domain.catalog` para reutilizar vocabulario compartido (`Language`,
`AnimeType`, `StreamQuality`, `Thumbnail`, ...); la dependencia es en un solo
sentido (`providers` -> `catalog`), nunca al revés: un proveedor existe para
servir contenido de catálogo, no lo contrario.

Estos VOs representan datos ya validados/tipados según nuestras reglas de
dominio. Lo que un provider concreto devuelve "en crudo" (strings sueltos,
campos con nombres específicos del proveedor) vive como DTOs en
`application/providers/dto.py` y se traduce a este vocabulario mediante la
normalización (`application/providers/normalizers.py`), nunca al revés.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from geekbaku.domain.catalog.value_objects import AnimeType, Language, StreamQuality, Thumbnail
from geekbaku.domain.shared.errors import ValidationError

_PROVIDER_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class ProviderId:
    """Identificador único y estable de un `StreamingProvider` (ej. 'provider-a')."""

    value: str

    def __post_init__(self) -> None:
        if not _PROVIDER_ID_PATTERN.match(self.value):
            raise ValidationError(
                f"'{self.value}' no es un ProviderId válido "
                "(debe ser kebab-case: minúsculas, dígitos y guiones)."
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ExternalReference:
    """Identifica una pieza de contenido dentro de un provider específico.

    Distinto de `catalog.ExternalId`: `ExternalId` vincula un Anime nuestro
    con un catálogo de metadata externo (MAL, AniList) para enriquecimiento;
    `ExternalReference` es la clave que el Provider Engine usa para pedirle
    a UN proveedor concreto el detalle/episodios de un contenido.
    """

    provider_id: ProviderId
    external_id: str

    def __post_init__(self) -> None:
        if not self.external_id.strip():
            raise ValidationError("El external_id de una ExternalReference no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Describe qué capacidades soporta un provider.

    El Provider Engine consulta estas banderas antes de invocar una
    capacidad (`application/providers/exceptions.py:ProviderCapabilityNotSupportedError`
    si se pide una no soportada), en vez de asumir que todo provider
    implementa el 100% de la interfaz de forma útil.
    """

    display_name: str
    supports_search: bool = True
    supports_latest: bool = True
    supports_popular: bool = True
    supports_genres: bool = True
    supports_types: bool = True

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("display_name no puede estar vacío en ProviderMetadata.")


@dataclass(frozen=True, slots=True)
class Source:
    """Fuente de reproducción resuelta en vivo por un provider.

    A diferencia de `catalog.StreamingSource` (entidad persistida en nuestro
    catálogo interno), `Source` es efímera: representa el resultado de
    preguntarle a un provider "¿dónde se reproduce esto ahora?", típicamente
    con URLs que expiran. La ingesta que convierte un `Source` en un
    `catalog.StreamingSource` persistido queda fuera de este sprint (no se
    implementa scraping/ingesta todavía).
    """

    reference: ExternalReference
    url: str
    quality: StreamQuality
    audio_language: Language | None = None
    subtitle_language: Language | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValidationError("La url de un Source no puede estar vacía.")


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Resultado liviano de una búsqueda cross-provider."""

    reference: ExternalReference
    title: str
    thumbnail: Thumbnail | None = None
    anime_type: AnimeType | None = None
    year: int | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("El título de un SearchResult no puede estar vacío.")


class ProviderStatus(StrEnum):
    """Estado operacional observado de un provider (ver `ProviderHealth`)."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Límite de peticiones que un provider permite en una ventana de tiempo."""

    max_requests: int
    period_seconds: float

    def __post_init__(self) -> None:
        if self.max_requests <= 0:
            raise ValidationError("max_requests debe ser mayor a 0.")
        if self.period_seconds <= 0:
            raise ValidationError("period_seconds debe ser mayor a 0.")


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Política de reintentos con backoff exponencial."""

    max_attempts: int = 3
    backoff_base_seconds: float = 0.5
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValidationError("max_attempts debe ser al menos 1.")
        if self.backoff_base_seconds < 0:
            raise ValidationError("backoff_base_seconds no puede ser negativo.")
        if self.backoff_multiplier < 1:
            raise ValidationError("backoff_multiplier debe ser >= 1.")


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Configuración de cache por provider (ver `application/providers/cache.py`)."""

    enabled: bool = True
    ttl_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.ttl_seconds < 0:
            raise ValidationError("ttl_seconds no puede ser negativo.")


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    """Configuración operacional (técnica) de un provider concreto.

    Distinta de `StreamingProvider` (entidad persistida en `entities.py` que
    representa si el provider está habilitado/su prioridad administrativa):
    `ProviderConfiguration` describe CÓMO se comporta técnicamente el
    proveedor (endpoint, timeout, límites, reintentos, cache), típicamente
    provista por configuración/entorno al construirlo vía `ProviderFactory`,
    no editada desde un panel de administración.
    """

    provider_id: ProviderId
    base_url: str
    timeout_seconds: float = 10.0
    rate_limit: RateLimitConfig | None = None
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValidationError("base_url no puede estar vacío en ProviderConfiguration.")
        if self.timeout_seconds <= 0:
            raise ValidationError("timeout_seconds debe ser mayor a 0.")


@dataclass(frozen=True, slots=True)
class Catalog:
    """Facetas de navegación (géneros, tipos) que expone un provider.

    No confundir con `application.catalog.ports.CatalogRepository`: ese
    puerto lee NUESTRO catálogo interno persistido; este VO describe lo que
    UN provider externo dice que soporta navegar (sus propios géneros/tipos,
    con nombres que aún no fueron normalizados a nuestro `AnimeType`/`Genre`).
    """

    provider_id: ProviderId
    genres: tuple[str, ...]
    types: tuple[str, ...]


__all__ = [
    "CacheConfig",
    "Catalog",
    "ExternalReference",
    "ProviderConfiguration",
    "ProviderId",
    "ProviderMetadata",
    "ProviderStatus",
    "RateLimitConfig",
    "RetryConfig",
    "SearchResult",
    "Source",
]
