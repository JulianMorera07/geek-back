"""Source Resolver.

Arma un `EpisodePlayback` (metadata + fuentes candidatas) a partir de un
episodio del catálogo interno ya cargado, y expone selección/priorización
delegando en `SourceSelectionService` (dominio puro: múltiples fuentes,
prioridad, fallback automático a la siguiente mejor calidad, múltiples
calidades).

Deliberadamente SIN cache ni I/O propios: resolver una lista de fuentes a
partir de un `Episode` ya cargado es una operación pura (mapping +
selección). El cacheo de la metadata resultante (nunca del progreso) es
responsabilidad del caso de uso que orquesta la carga real desde el
repositorio (`use_cases/get_episode_playback.py`), que es donde vive el I/O.
"""

from __future__ import annotations

from geekbaku.application.playback.mappers import to_playback_metadata, to_playback_source
from geekbaku.domain.catalog.entities import Anime, Episode, Season
from geekbaku.domain.catalog.value_objects import StreamQuality
from geekbaku.domain.playback.entities import EpisodePlayback, PlaybackSource
from geekbaku.domain.playback.services import SourceSelectionService


class SourceResolver:
    def __init__(self, provider_priorities: dict[str, int] | None = None) -> None:
        self._provider_priorities = provider_priorities or {}

    def resolve(self, anime: Anime, season: Season, episode: Episode) -> EpisodePlayback:
        metadata = to_playback_metadata(anime, season, episode)
        sources = tuple(
            source
            for streaming_source in episode.streaming_sources
            if (
                source := to_playback_source(
                    streaming_source,
                    self._provider_priorities.get(streaming_source.provider_name, 0),
                )
            )
            is not None
        )
        return EpisodePlayback(episode_id=episode.id, metadata=metadata, sources=sources)

    def select_best(
        self, episode_playback: EpisodePlayback, preferred_quality: StreamQuality | None = None
    ) -> PlaybackSource:
        preferred_provider_ids = tuple(
            sorted(self._provider_priorities, key=lambda p: -self._provider_priorities[p])
        )
        return SourceSelectionService.select_best(
            episode_playback.sources,
            preferred_quality=preferred_quality,
            preferred_provider_ids=preferred_provider_ids,
        )

    def select_by_quality(
        self, episode_playback: EpisodePlayback, quality: StreamQuality
    ) -> PlaybackSource:
        return SourceSelectionService.select_by_quality(episode_playback.sources, quality)
