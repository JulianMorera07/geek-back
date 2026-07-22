"""Métricas del Aggregation Engine.

Distintas de `ProviderStats` (Sprint 5, `application/providers/stats.py`),
que es por-provider: `AggregationMetrics` mide el comportamiento del proceso
de agregación en sí — cuántas veces se agregó, cuántos resultados crudos
entraron vs. cuántos quedaron tras deduplicar, hit rate de la cache de
resultados agregados. Puramente observacional.
"""

from __future__ import annotations


class AggregationMetrics:
    def __init__(self) -> None:
        self.total_aggregations = 0
        self.total_raw_results = 0
        self.total_merged_results = 0
        self.total_duplicates_merged = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_aggregation(self, raw_count: int, merged_count: int) -> None:
        self.total_aggregations += 1
        self.total_raw_results += raw_count
        self.total_merged_results += merged_count
        self.total_duplicates_merged += max(0, raw_count - merged_count)

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    @property
    def average_raw_results_per_aggregation(self) -> float:
        if self.total_aggregations == 0:
            return 0.0
        return self.total_raw_results / self.total_aggregations

    @property
    def deduplication_rate(self) -> float:
        """Fracción de resultados crudos que resultaron ser duplicados."""
        if self.total_raw_results == 0:
            return 0.0
        return self.total_duplicates_merged / self.total_raw_results

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
