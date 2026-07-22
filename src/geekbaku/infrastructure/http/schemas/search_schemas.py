"""Schemas Pydantic de búsqueda/descubrimiento distribuido (Aggregation
Engine). Se traducen desde `application/aggregation/dto.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceReferenceSchema(BaseModel):
    """Un provider concreto que contribuyó a un resultado agregado."""

    provider_id: str = Field(examples=["jikan"])
    external_id: str = Field(examples=["16498"])
    priority: int
    response_time_ms: float


class AggregatedSearchResultSchema(BaseModel):
    title: str = Field(examples=["Shingeki no Kyojin"])
    thumbnail_url: str | None = None
    anime_type: str | None = Field(default=None, examples=["TV"])
    year: int | None = Field(default=None, examples=[2013])
    sources: tuple[SourceReferenceSchema, ...] = ()
    completeness_score: float = Field(examples=[0.75], ge=0.0, le=1.0)
    quality_score: float = Field(examples=[0.85], ge=0.0, le=1.0)
