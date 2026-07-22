"""Schemas Pydantic del estado público de providers registrados."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderInfoSchema(BaseModel):
    provider_id: str = Field(examples=["jikan"])
    display_name: str = Field(examples=["Jikan (MyAnimeList)"])
    is_enabled: bool
    priority: int
    health_status: str = Field(examples=["healthy"])
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_response_time_ms: float
