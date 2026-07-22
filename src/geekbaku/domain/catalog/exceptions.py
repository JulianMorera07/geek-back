"""Excepciones de dominio específicas del catálogo.

Todas heredan de las excepciones base en `geekbaku.domain.shared.errors` para
que la capa de infraestructura pueda manejarlas genéricamente si lo necesita,
pero exponen tipos concretos para que los casos de uso puedan reaccionar a
errores específicos cuando haga falta.
"""

from __future__ import annotations

from geekbaku.domain.shared.errors import ConflictError, NotFoundError, ValidationError


class AnimeNotFoundError(NotFoundError):
    """No existe un Anime con el id/slug solicitado."""


class SeasonNotFoundError(NotFoundError):
    """No existe una Season con el id solicitado dentro del Anime."""


class EpisodeNotFoundError(NotFoundError):
    """No existe un Episode con el id solicitado."""


class GenreNotFoundError(NotFoundError):
    """No existe un Genre con el id/slug solicitado."""


class StudioNotFoundError(NotFoundError):
    """No existe un Studio con el id/slug solicitado."""


class ProducerNotFoundError(NotFoundError):
    """No existe un Producer con el id/slug solicitado."""


class TagNotFoundError(NotFoundError):
    """No existe un Tag con el id/slug solicitado."""


class StreamingSourceNotFoundError(NotFoundError):
    """No existe una StreamingSource con el id solicitado dentro del Episode."""


class DuplicateSlugError(ConflictError):
    """Ya existe una entidad con ese slug."""


class DuplicateSeasonNumberError(ConflictError):
    """Ya existe una Season con ese número dentro del Anime."""


class DuplicateEpisodeNumberError(ConflictError):
    """Ya existe un Episode con ese número dentro de la Season."""


class DuplicateExternalIdError(ConflictError):
    """Ya existe un ExternalId con esa fuente para esta entidad."""


class DuplicateStreamingSourceError(ConflictError):
    """Ya existe una StreamingSource con el mismo (provider, external_ref)."""


class DuplicateRelationError(ConflictError):
    """Ya existe una Relation de ese tipo hacia el mismo Anime."""


class SelfRelationError(ValidationError):
    """Un Anime no puede tener una Relation hacia sí mismo."""


class InvalidStatusTransitionError(ValidationError):
    """La transición de AnimeStatus solicitada no es válida."""
