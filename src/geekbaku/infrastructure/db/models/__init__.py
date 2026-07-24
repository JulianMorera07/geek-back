"""Registro central de modelos ORM: importarlos aquí asegura que estén
adjuntos a `Base.metadata` antes de que Alembic autogenere migraciones.
"""

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

__all__ = [
    "AnimeModel",
    "EpisodeModel",
    "GenreModel",
    "ProducerModel",
    "SeasonModel",
    "StreamingSourceModel",
    "StudioModel",
    "TagModel",
]
