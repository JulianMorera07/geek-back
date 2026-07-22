"""Excepciones de dominio del módulo de reproducción."""

from __future__ import annotations

from geekbaku.domain.shared.errors import NotFoundError, ValidationError


class PlaybackSessionNotFoundError(NotFoundError):
    """No existe una PlaybackSession con el id solicitado."""


class SourceNotFoundError(NotFoundError):
    """No existe una PlaybackSource con el id solicitado en este episodio."""


class NoAvailableSourceError(NotFoundError):
    """No hay ninguna PlaybackSource activa/vigente para este episodio."""


class QualityNotAvailableError(NotFoundError):
    """La calidad solicitada no está disponible entre las fuentes del episodio."""


class SubtitleNotAvailableError(NotFoundError):
    """El idioma de subtítulo solicitado no está disponible entre las fuentes."""


class InvalidSessionTransitionError(ValidationError):
    """La transición de PlaybackSessionStatus solicitada no es válida."""
