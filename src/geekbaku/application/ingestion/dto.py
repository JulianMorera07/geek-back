"""Commands del módulo de ingesta."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngestAnimeCommand:
    provider_id: str
    external_id: str


__all__ = ["IngestAnimeCommand"]
