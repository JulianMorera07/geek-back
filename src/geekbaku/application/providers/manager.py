"""Provider Manager: orquesta el ciclo de vida de cada llamada a un provider.

Es el componente central del Provider Framework. Compone, en este orden,
por cada llamada:

1. `ProviderCache` (opcional) — sirve la respuesta cacheada si hay un hit.
2. `CircuitBreaker` — si está `OPEN` para ese provider, no llama (intenta
   `Fallback` o lanza `ProviderCircuitOpenError`).
3. `RateLimiter` — corta antes de llamar si el provider excedió su cupo.
4. Timeout (`ProviderConfiguration.timeout_seconds`) + `RetryPolicy` — cada
   intento tiene su propio timeout; se reintenta con backoff si falla.
5. `HealthTracker` + `CircuitBreaker` + `StatsTracker` — se actualizan según
   el resultado (éxito o falla final).
6. Fallback — si la llamada falló definitivamente (o el breaker estaba
   `OPEN`) y hay un último valor bueno conocido cacheado, se sirve ese en
   vez de propagar el error.
7. `logging` — cada etapa deja rastro (provider, operación, tiempo de
   respuesta, reintentos, errores).

Todas las operaciones de adquisición de datos (`search`, `get_anime_detail`,
`get_episodes`, `get_seasons`, `get_related`, `get_latest`, `get_popular`,
`get_genres`, `get_types`) pasan por el mismo despacho (`_dispatch` /
`_fan_out`), así que todo lo anterior aplica uniformemente sin importar la
operación ni el provider.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence

from geekbaku.application.common.pagination import Pagination
from geekbaku.application.providers.cache import ProviderCache, build_cache_key
from geekbaku.application.providers.circuit_breaker import CircuitBreaker
from geekbaku.application.providers.dto import (
    ProviderAnimeDTO,
    ProviderCatalogDTO,
    ProviderEpisodeDTO,
    ProviderRelatedDTO,
    ProviderSeasonDTO,
    SearchResultDTO,
)
from geekbaku.application.providers.exceptions import ProviderCircuitOpenError
from geekbaku.application.providers.health import HealthTracker
from geekbaku.application.providers.ports import ProviderPort
from geekbaku.application.providers.rate_limiter import RateLimiter
from geekbaku.application.providers.registry import ProviderRegistry
from geekbaku.application.providers.retry import RetryPolicy
from geekbaku.application.providers.stats import ProviderStats, StatsTracker
from geekbaku.domain.providers.entities import ProviderHealth
from geekbaku.domain.providers.exceptions import (
    ProviderRateLimitExceededError,
    ProviderRequestError,
)
from geekbaku.domain.providers.value_objects import (
    ExternalReference,
    ProviderConfiguration,
    ProviderId,
    ProviderMetadata,
    RetryConfig,
)

logger = logging.getLogger("geekbaku.providers")

_DEFAULT_TIMEOUT_SECONDS = 10.0


class ProviderManager:
    """Punto único de acceso a los providers registrados."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        health_tracker: HealthTracker | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        stats_tracker: StatsTracker | None = None,
        cache: ProviderCache | None = None,
        enable_fallback: bool = True,
    ) -> None:
        self.registry = registry or ProviderRegistry()
        self._health = health_tracker or HealthTracker()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._retry_policy = retry_policy or RetryPolicy()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._stats = stats_tracker or StatsTracker()
        self._cache = cache
        self._enable_fallback = enable_fallback
        self._last_good: dict[str, object] = {}

    # -- registro (delega en ProviderRegistry, firma compatible con Sprint 3/4) --

    def register(
        self,
        provider_id: ProviderId,
        adapter: ProviderPort,
        *,
        metadata: ProviderMetadata | None = None,
        priority: int = 0,
        is_enabled: bool = True,
        configuration: ProviderConfiguration | None = None,
    ) -> None:
        self.registry.register(
            provider_id,
            adapter,
            metadata=metadata,
            priority=priority,
            is_enabled=is_enabled,
            configuration=configuration,
        )

    def unregister(self, provider_id: ProviderId) -> None:
        self.registry.unregister(provider_id)

    def get(self, provider_id: ProviderId) -> ProviderPort:
        return self.registry.get_adapter(provider_id)

    def list_provider_ids(self) -> tuple[ProviderId, ...]:
        return self.registry.list_provider_ids()

    def enable(self, provider_id: ProviderId) -> None:
        """Habilita dinámicamente un provider (vuelve a participar en fan-out)."""
        self.registry.enable(provider_id)

    def disable(self, provider_id: ProviderId) -> None:
        """Deshabilita dinámicamente un provider (se excluye de fan-out; una
        llamada dirigida a él por `provider_ids` explícito sigue funcionando).
        """
        self.registry.disable(provider_id)

    def get_health(self, provider_id: ProviderId) -> ProviderHealth:
        return self._health.get(provider_id)

    def get_stats(self, provider_id: ProviderId) -> ProviderStats:
        return self._stats.get(provider_id)

    def get_all_stats(self) -> dict[ProviderId, ProviderStats]:
        return self._stats.get_all()

    # -- cache: invalidación explícita ------------------------------------------

    async def invalidate_cache(self, operation: str, provider_id: ProviderId, *parts: str) -> None:
        if self._cache is None:
            return
        await self._cache.invalidate(self._cache_key(operation, provider_id, *parts))

    async def invalidate_provider_cache(self, provider_id: ProviderId) -> None:
        """Invalida toda entrada de cache asociada a un provider."""
        if self._cache is None:
            return
        marker = f":{provider_id}:"
        suffix = f":{provider_id}"
        await self._cache.invalidate_matching(
            lambda key: marker in key or key.endswith(suffix)
        )

    # -- operaciones sobre UN provider ------------------------------------------

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None:
        cache_key = self._cache_key(
            "get_anime_detail", reference.provider_id, reference.external_id
        )
        return await self._dispatch(
            reference.provider_id,
            "get_anime_detail",
            lambda adapter: adapter.get_anime_detail(reference),
            cache_key=cache_key,
        )

    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]:
        cache_key = self._cache_key(
            "get_episodes", reference.provider_id, reference.external_id
        )
        return await self._dispatch(
            reference.provider_id,
            "get_episodes",
            lambda adapter: adapter.get_episodes(reference),
            cache_key=cache_key,
        )

    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]:
        cache_key = self._cache_key("get_seasons", reference.provider_id, reference.external_id)
        return await self._dispatch(
            reference.provider_id,
            "get_seasons",
            lambda adapter: adapter.get_seasons(reference),
            cache_key=cache_key,
        )

    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]:
        cache_key = self._cache_key("get_related", reference.provider_id, reference.external_id)
        return await self._dispatch(
            reference.provider_id,
            "get_related",
            lambda adapter: adapter.get_related(reference),
            cache_key=cache_key,
        )

    async def get_genres(self, provider_id: ProviderId) -> list[str]:
        cache_key = self._cache_key("get_genres", provider_id)
        return await self._dispatch(
            provider_id, "get_genres", lambda adapter: adapter.get_genres(), cache_key=cache_key
        )

    async def get_types(self, provider_id: ProviderId) -> list[str]:
        cache_key = self._cache_key("get_types", provider_id)
        return await self._dispatch(
            provider_id, "get_types", lambda adapter: adapter.get_types(), cache_key=cache_key
        )

    async def get_catalog(self, provider_id: ProviderId) -> ProviderCatalogDTO:
        genres = await self.get_genres(provider_id)
        types = await self.get_types(provider_id)
        return ProviderCatalogDTO(
            provider_id=str(provider_id), genres=tuple(genres), types=tuple(types)
        )

    # -- operaciones agregadas sobre VARIOS providers -------------------------

    async def search(
        self,
        query: str,
        pagination: Pagination,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[SearchResultDTO]:
        return await self._fan_out(
            provider_ids,
            "search",
            lambda adapter: adapter.search(query, pagination),
            lambda provider_id: self._cache_key(
                "search", provider_id, query, str(pagination.page), str(pagination.page_size)
            ),
        )

    async def get_latest(
        self,
        pagination: Pagination,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[SearchResultDTO]:
        return await self._fan_out(
            provider_ids,
            "get_latest",
            lambda adapter: adapter.get_latest(pagination),
            lambda provider_id: self._cache_key(
                "get_latest", provider_id, str(pagination.page), str(pagination.page_size)
            ),
        )

    async def get_popular(
        self,
        pagination: Pagination,
        provider_ids: Sequence[ProviderId] | None = None,
    ) -> list[SearchResultDTO]:
        return await self._fan_out(
            provider_ids,
            "get_popular",
            lambda adapter: adapter.get_popular(pagination),
            lambda provider_id: self._cache_key(
                "get_popular", provider_id, str(pagination.page), str(pagination.page_size)
            ),
        )

    # -- despacho de una llamada a UN provider ----------------------------------

    async def _dispatch[T](
        self,
        provider_id: ProviderId,
        operation: str,
        call: Callable[[ProviderPort], Awaitable[T]],
        *,
        cache_key: str | None = None,
    ) -> T:
        registration = self.registry.get(provider_id)
        configuration = registration.configuration

        cache_enabled = (
            cache_key is not None
            and self._cache is not None
            and (configuration is None or configuration.cache.enabled)
        )
        if cache_enabled:
            assert self._cache is not None and cache_key is not None
            cached = await self._cache.get(cache_key)
            if cached is not None:
                self._stats.record_cache_hit(provider_id)
                logger.debug(
                    "provider_cache_hit provider=%s operation=%s", provider_id, operation
                )
                return cached  # type: ignore[return-value]
            self._stats.record_cache_miss(provider_id)

        if not self._circuit_breaker.allow_call(provider_id):
            self._stats.record_circuit_rejected(provider_id)
            logger.warning(
                "provider_circuit_open provider=%s operation=%s", provider_id, operation
            )
            fallback = self._try_fallback(provider_id, cache_key)
            if fallback is not _NO_FALLBACK:
                return fallback  # type: ignore[return-value]
            raise ProviderCircuitOpenError(
                f"El circuit breaker de '{provider_id}' está abierto; no se intentó la llamada."
            )

        rate_limit = configuration.rate_limit if configuration else None
        if not self._rate_limiter.allow(provider_id, rate_limit):
            self._stats.record_rate_limited(provider_id)
            logger.warning(
                "provider_rate_limited provider=%s operation=%s", provider_id, operation
            )
            raise ProviderRateLimitExceededError(
                f"Rate limit excedido para el provider '{provider_id}'."
            )

        retry_config = configuration.retry if configuration else RetryConfig()
        timeout_seconds = (
            configuration.timeout_seconds if configuration else _DEFAULT_TIMEOUT_SECONDS
        )
        attempts_used = 0

        def on_retry(attempt: int, exc: Exception) -> None:
            nonlocal attempts_used
            attempts_used = attempt
            self._stats.record_retry(provider_id)
            logger.warning(
                "provider_retry provider=%s operation=%s attempt=%d error=%s",
                provider_id,
                operation,
                attempt,
                exc,
            )

        async def attempt() -> T:
            return await asyncio.wait_for(call(registration.adapter), timeout=timeout_seconds)

        start = time.monotonic()
        try:
            result = await self._retry_policy.run(retry_config, attempt, on_retry=on_retry)
        except Exception as exc:  # noqa: BLE001 - se re-envuelve deliberadamente
            elapsed_ms = (time.monotonic() - start) * 1000
            self._health.record_failure(provider_id, str(exc))
            self._circuit_breaker.record_failure(provider_id)
            self._stats.record_failure(provider_id, str(exc))
            logger.error(
                "provider_call_failed provider=%s operation=%s elapsed_ms=%.1f "
                "retries=%d error=%s",
                provider_id,
                operation,
                elapsed_ms,
                attempts_used,
                exc,
            )

            fallback = self._try_fallback(provider_id, cache_key)
            if fallback is not _NO_FALLBACK:
                return fallback  # type: ignore[return-value]

            raise ProviderRequestError(
                f"La operación '{operation}' falló para el provider '{provider_id}': {exc}"
            ) from exc

        elapsed_ms = (time.monotonic() - start) * 1000
        self._health.record_success(provider_id)
        self._circuit_breaker.record_success(provider_id)
        self._stats.record_success(provider_id, elapsed_ms)
        logger.info(
            "provider_call_succeeded provider=%s operation=%s elapsed_ms=%.1f",
            provider_id,
            operation,
            elapsed_ms,
        )

        if cache_key is not None:
            if self._enable_fallback:
                self._last_good[cache_key] = result
            if cache_enabled:
                assert self._cache is not None
                ttl = configuration.cache.ttl_seconds if configuration else 300.0
                await self._cache.set(cache_key, result, ttl)

        return result

    def _try_fallback(self, provider_id: ProviderId, cache_key: str | None) -> object:
        if not self._enable_fallback or cache_key is None or cache_key not in self._last_good:
            return _NO_FALLBACK
        self._stats.record_fallback_used(provider_id)
        logger.warning(
            "provider_fallback_used provider=%s cache_key=%s", provider_id, cache_key
        )
        return self._last_good[cache_key]

    # -- despacho agregado sobre VARIOS providers -------------------------------

    async def _fan_out(
        self,
        provider_ids: Sequence[ProviderId] | None,
        operation: str,
        call: Callable[[ProviderPort], Awaitable[list[SearchResultDTO]]],
        cache_key_for: Callable[[ProviderId], str],
    ) -> list[SearchResultDTO]:
        if provider_ids is not None:
            targets: tuple[ProviderId, ...] = tuple(provider_ids)
        else:
            targets = tuple(
                registration.provider.id
                for registration in self.registry.list_enabled_by_priority()
                if self._health.is_available(registration.provider.id)
            )

        results = await asyncio.gather(
            *(
                self._dispatch(provider_id, operation, call, cache_key=cache_key_for(provider_id))
                for provider_id in targets
            ),
            return_exceptions=True,
        )

        aggregated: list[SearchResultDTO] = []
        for result in results:
            if isinstance(result, BaseException):
                continue  # falla aislada: se omite ese provider del agregado
            aggregated.extend(result)
        return aggregated

    @staticmethod
    def _cache_key(operation: str, provider_id: ProviderId, *parts: str) -> str:
        return build_cache_key(operation, str(provider_id), *parts)


class _NoFallback:
    """Sentinel distinguible de cualquier valor real (incluido `None`, un
    resultado válido de `get_anime_detail`), para saber si hubo fallback.
    """

    __slots__ = ()


_NO_FALLBACK = _NoFallback()
