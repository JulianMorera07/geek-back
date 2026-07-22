"""Aggregation Engine.

Consulta múltiples providers a través del Provider Framework
(`ProviderManager`, Sprint 4/5) y devuelve una única respuesta normalizada,
deduplicada, fusionada y ordenada.

Deliberadamente NO reimplementa nada que `ProviderManager` ya resuelve de
forma genérica por-provider: consultas paralelas, prioridad, fallback
automático, timeouts, cancelación de providers lentos (`asyncio.wait_for`
cancela la tarea subyacente), circuit breaker, rate limiting, métricas y
logs por-provider. Este motor se apoya en `ProviderManager.search`/
`get_latest`/`get_popular` (que ya hacen fan-out paralelo con toda esa
resiliencia) y agrega, sobre el resultado, lo que es nuevo en este sprint:
Deduplication Engine, Ranking Engine, y una cache/métricas propias del nivel
agregado (distintas de las por-provider).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence

from geekbaku.application.aggregation import deduplication, ranking
from geekbaku.application.aggregation.dto import AggregatedAnimeDTO, AggregatedSearchResultDTO
from geekbaku.application.aggregation.metrics import AggregationMetrics
from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import ProviderCache, build_cache_key
from geekbaku.application.providers.dto import (
    ExternalReferenceDTO,
    NormalizedAnimeDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.mappers import parse_external_reference
from geekbaku.application.providers.normalizers import to_normalized_anime
from geekbaku.domain.providers.value_objects import ProviderId

_ListingCall = Callable[
    [Pagination, "Sequence[ProviderId] | None"], Awaitable[list[SearchResultDTO]]
]

logger = logging.getLogger("geekbaku.aggregation")

_DEFAULT_CACHE_TTL_SECONDS = 300.0


class AggregationEngine:
    def __init__(
        self,
        manager: ProviderManager,
        cache: ProviderCache | None = None,
        cache_ttl_seconds: float = _DEFAULT_CACHE_TTL_SECONDS,
        metrics: AggregationMetrics | None = None,
    ) -> None:
        self._manager = manager
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds
        self.metrics = metrics or AggregationMetrics()

    # -- contexto compartido para deduplicación/ranking -------------------------

    def _provider_priorities(self) -> dict[str, int]:
        return {
            str(registration.provider.id): registration.provider.priority
            for registration in self._manager.registry.list_all()
        }

    def _provider_response_times(self) -> dict[str, float]:
        return {
            str(provider_id): stats.average_response_time_ms
            for provider_id, stats in self._manager.get_all_stats().items()
        }

    # -- cache de resultados agregados ------------------------------------------

    async def _cache_get(self, key: str) -> object | None:
        if self._cache is None:
            return None
        cached = await self._cache.get(key)
        if cached is not None:
            self.metrics.record_cache_hit()
        else:
            self.metrics.record_cache_miss()
        return cached

    async def _cache_set(self, key: str, value: object) -> None:
        if self._cache is not None:
            await self._cache.set(key, value, self._cache_ttl_seconds)

    async def invalidate_search_cache(
        self, query: str, pagination: Pagination, provider_ids: Sequence[ProviderId] | None = None
    ) -> None:
        if self._cache is None:
            return
        await self._cache.invalidate(self._search_cache_key(query, pagination, provider_ids))

    async def invalidate_all_cache(self) -> None:
        """Invalida toda entrada de cache producida por este engine (no
        toca la cache por-provider de `ProviderManager`, que es un store
        independiente)."""
        if self._cache is None:
            return
        await self._cache.invalidate_matching(lambda _key: True)

    @staticmethod
    def _search_cache_key(
        query: str, pagination: Pagination, provider_ids: Sequence[ProviderId] | None
    ) -> str:
        providers_part = ",".join(sorted(str(p) for p in provider_ids)) if provider_ids else "*"
        return build_cache_key(
            "aggregated_search",
            query,
            str(pagination.page),
            str(pagination.page_size),
            providers_part,
        )

    # -- búsqueda agregada (Search Engine) --------------------------------------

    async def search(
        self,
        query: str,
        pagination: Pagination | None = None,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[AggregatedSearchResultDTO]:
        pagination = pagination or Pagination()
        cache_key = self._search_cache_key(query, pagination, provider_ids)

        cached = await self._cache_get(cache_key)
        if cached is not None:
            logger.debug("aggregation_cache_hit operation=search query=%s", query)
            return cached  # type: ignore[return-value]

        start = time.monotonic()
        raw_results = await self._manager.search(query, pagination, provider_ids)
        elapsed_ms = (time.monotonic() - start) * 1000

        ranked = self._merge_and_rank_search_results(raw_results)

        logger.info(
            "aggregation_search_completed query=%s raw=%d merged=%d elapsed_ms=%.1f",
            query,
            len(raw_results),
            len(ranked),
            elapsed_ms,
        )

        await self._cache_set(cache_key, ranked)
        return ranked

    async def get_latest(
        self,
        pagination: Pagination | None = None,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[AggregatedSearchResultDTO]:
        return await self._aggregate_listing(
            "get_latest", self._manager.get_latest, pagination, provider_ids
        )

    async def get_popular(
        self,
        pagination: Pagination | None = None,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[AggregatedSearchResultDTO]:
        return await self._aggregate_listing(
            "get_popular", self._manager.get_popular, pagination, provider_ids
        )

    async def _aggregate_listing(
        self,
        operation: str,
        call: _ListingCall,
        pagination: Pagination | None,
        provider_ids: Sequence[ProviderId] | None,
    ) -> list[AggregatedSearchResultDTO]:
        pagination = pagination or Pagination()
        providers_part = ",".join(sorted(str(p) for p in provider_ids)) if provider_ids else "*"
        cache_key = build_cache_key(
            f"aggregated_{operation}",
            str(pagination.page),
            str(pagination.page_size),
            providers_part,
        )

        cached = await self._cache_get(cache_key)
        if cached is not None:
            logger.debug("aggregation_cache_hit operation=%s", operation)
            return cached  # type: ignore[return-value]

        start = time.monotonic()
        raw_results = await call(pagination, provider_ids)
        elapsed_ms = (time.monotonic() - start) * 1000

        ranked = self._merge_and_rank_search_results(raw_results)

        logger.info(
            "aggregation_%s_completed raw=%d merged=%d elapsed_ms=%.1f",
            operation,
            len(raw_results),
            len(ranked),
            elapsed_ms,
        )

        await self._cache_set(cache_key, ranked)
        return ranked

    def _merge_and_rank_search_results(
        self, raw_results: list[SearchResultDTO]
    ) -> list[AggregatedSearchResultDTO]:
        priorities = self._provider_priorities()
        response_times = self._provider_response_times()

        groups = deduplication.group_search_results(raw_results)
        merged = [
            deduplication.merge_search_results(group, priorities, response_times)
            for group in groups
        ]
        ranked = ranking.rank_search_results(merged)

        self.metrics.record_aggregation(raw_count=len(raw_results), merged_count=len(ranked))
        return ranked

    # -- detalle agregado --------------------------------------------------------

    async def aggregate_detail(
        self, references: Sequence[ExternalReferenceDTO]
    ) -> AggregatedAnimeDTO | None:
        """Fusiona el detalle de un mismo anime reportado por varios
        providers. Asume que `references` ya corresponden al mismo anime
        real (ej. obtenidas de agrupar resultados de `search` previamente
        con `deduplication.group_search_results`) — NO vuelve a deduplicar,
        solo fusiona lo que ya se sabe que es lo mismo.
        """
        if not references:
            return None

        cache_key = build_cache_key(
            "aggregated_detail",
            ",".join(sorted(f"{r.provider_id}:{r.external_id}" for r in references)),
        )
        cached = await self._cache_get(cache_key)
        if cached is not None:
            logger.debug("aggregation_cache_hit operation=aggregate_detail")
            return cached  # type: ignore[return-value]

        start = time.monotonic()
        results = await asyncio.gather(*(self._fetch_normalized(r) for r in references))
        elapsed_ms = (time.monotonic() - start) * 1000
        normalized = [r for r in results if r is not None]

        if not normalized:
            logger.warning(
                "aggregation_detail_empty references=%d elapsed_ms=%.1f",
                len(references),
                elapsed_ms,
            )
            return None

        priorities = self._provider_priorities()
        response_times = self._provider_response_times()
        merged = deduplication.merge_normalized_anime(normalized, priorities, response_times)
        ranked = ranking.rank_anime([merged])[0]

        self.metrics.record_aggregation(raw_count=len(references), merged_count=1)
        logger.info(
            "aggregation_detail_completed references=%d contributing=%d elapsed_ms=%.1f",
            len(references),
            len(normalized),
            elapsed_ms,
        )

        await self._cache_set(cache_key, ranked)
        return ranked

    async def _fetch_normalized(
        self, reference: ExternalReferenceDTO
    ) -> NormalizedAnimeDTO | None:
        try:
            parsed = parse_external_reference(reference)
            raw = await self._manager.get_anime_detail(parsed)
        except Exception as exc:  # noqa: BLE001 - falla aislada por provider
            logger.warning(
                "aggregation_detail_fetch_failed provider=%s external_id=%s error=%s",
                reference.provider_id,
                reference.external_id,
                exc,
            )
            return None
        if raw is None:
            return None
        return to_normalized_anime(raw)
