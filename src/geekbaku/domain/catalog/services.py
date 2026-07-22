"""Domain Services del catálogo.

Un Domain Service se usa cuando una regla de negocio no pertenece
naturalmente a una única entidad/agregado. Ambos servicios de este módulo
son puros (no hacen I/O ni conocen repositorios): reciben agregados ya
cargados y devuelven/mutan datos en memoria. La orquestación de carga y
persistencia es responsabilidad de la capa de aplicación (casos de uso).
"""

from __future__ import annotations

from geekbaku.domain.catalog.entities import Anime, Episode, StreamingSource
from geekbaku.domain.catalog.value_objects import (
    RELATION_INVERSE,
    STREAM_QUALITY_RANK,
    Relation,
    RelationType,
)


class RelationLinkingService:
    """Crea relaciones narrativas consistentes entre dos Anime.

    Al vincular `source` -> `target` con un `RelationType`, agrega también la
    relación inversa correspondiente en `target` -> `source` (ej. SEQUEL en
    un sentido implica PREQUEL en el otro), para que el grafo de relaciones
    sea siempre bidireccionalmente consistente.
    """

    @staticmethod
    def link(source: Anime, target: Anime, relation_type: RelationType) -> None:
        source.add_relation(Relation(related_anime_id=target.id, relation_type=relation_type))
        inverse_type = RELATION_INVERSE[relation_type]
        target.add_relation(Relation(related_anime_id=source.id, relation_type=inverse_type))


class EpisodeAvailabilityService:
    """Determina disponibilidad y selecciona la mejor fuente de un Episode."""

    @staticmethod
    def is_available(episode: Episode) -> bool:
        """Un Episode está disponible si tiene al menos una fuente activa."""
        return any(source.is_active for source in episode.streaming_sources)

    @staticmethod
    def best_source(episode: Episode) -> StreamingSource | None:
        """Elige la fuente activa de mayor calidad disponible.

        Devuelve `None` si no hay ninguna fuente activa. Ante empate de
        calidad, se conserva el orden de inserción (se prefiere la primera
        encontrada), de modo que la elección sea determinística.
        """
        active_sources = [source for source in episode.streaming_sources if source.is_active]
        if not active_sources:
            return None
        return max(active_sources, key=lambda source: STREAM_QUALITY_RANK[source.quality])
