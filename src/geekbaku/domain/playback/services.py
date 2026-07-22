"""Domain Services del módulo de reproducción.

Ambos son puros (sin I/O): reciben datos ya cargados y deciden. La
orquestación de I/O real (traer las fuentes desde el catálogo/providers)
vive en `application/playback/source_resolver.py`, que usa
`SourceSelectionService` como su algoritmo de selección.
"""

from __future__ import annotations

from collections.abc import Sequence

from geekbaku.domain.catalog.value_objects import STREAM_QUALITY_RANK, StreamQuality
from geekbaku.domain.playback.entities import PlaybackSource
from geekbaku.domain.playback.exceptions import NoAvailableSourceError, QualityNotAvailableError
from geekbaku.domain.playback.value_objects import ResumePoint, WatchProgress

#: Progreso >= a este umbral (fracción de la duración) se considera
#: "terminado": reanudar debería empezar de nuevo, no 3 segundos antes del
#: final.
_NEAR_COMPLETE_THRESHOLD = 0.95

#: Progreso <= a este umbral se considera insignificante: no hay nada real
#: que "reanudar", se trata como si no hubiera progreso guardado.
_NEAR_START_THRESHOLD = 0.02


class SourceSelectionService:
    """Prioriza, filtra y selecciona entre `PlaybackSource` candidatas
    (Source Resolver: soporta múltiples fuentes, prioridad, fallback y
    múltiples calidades).
    """

    @staticmethod
    def rank(
        sources: Sequence[PlaybackSource],
        preferred_quality: StreamQuality | None = None,
        preferred_provider_ids: Sequence[str] | None = None,
    ) -> list[PlaybackSource]:
        """Ordena las fuentes DISPONIBLES (activas y no vencidas) de mejor a
        peor candidata. Si ninguna coincide con `preferred_quality`, no se
        excluyen: caen más abajo en el orden (fallback automático a la
        siguiente mejor calidad disponible).
        """
        available = [s for s in sources if s.is_available()]
        provider_rank = {
            provider_id: index for index, provider_id in enumerate(preferred_provider_ids or ())
        }

        def sort_key(source: PlaybackSource) -> tuple[int, int, int, int]:
            quality_matches = 0 if source.quality == preferred_quality else 1
            explicit_provider_rank = provider_rank.get(
                source.provider.provider_id, len(provider_rank)
            )
            return (
                quality_matches,
                explicit_provider_rank,
                -source.provider.priority,
                -STREAM_QUALITY_RANK[source.quality],
            )

        return sorted(available, key=sort_key)

    @staticmethod
    def select_best(
        sources: Sequence[PlaybackSource],
        preferred_quality: StreamQuality | None = None,
        preferred_provider_ids: Sequence[str] | None = None,
    ) -> PlaybackSource:
        ranked = SourceSelectionService.rank(sources, preferred_quality, preferred_provider_ids)
        if not ranked:
            raise NoAvailableSourceError("No hay ninguna fuente disponible para este episodio.")
        return ranked[0]

    @staticmethod
    def select_by_quality(
        sources: Sequence[PlaybackSource], quality: StreamQuality
    ) -> PlaybackSource:
        for source in SourceSelectionService.rank(sources):
            if source.quality == quality:
                return source
        raise QualityNotAvailableError(f"La calidad '{quality}' no está disponible.")


class ResumePointService:
    """Calcula desde dónde debería reanudarse la reproducción."""

    @staticmethod
    def compute(progress: WatchProgress | None) -> ResumePoint:
        if progress is None:
            return ResumePoint(position_seconds=0, is_completed=False)

        ratio = progress.position_seconds / progress.duration_seconds
        if ratio >= _NEAR_COMPLETE_THRESHOLD:
            return ResumePoint(position_seconds=0, is_completed=True)
        if ratio <= _NEAR_START_THRESHOLD:
            return ResumePoint(position_seconds=0, is_completed=False)
        return ResumePoint(position_seconds=progress.position_seconds, is_completed=False)
