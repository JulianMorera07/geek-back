"""Composition root a nivel de request.

Define los `Depends()` que resuelven casos de uso concretos para los
routers. Los providers "singleton" (`@lru_cache`) devuelven la misma
instancia durante la vida del proceso — apropiado para stores in-memory
como `InMemoryPlaybackSessionRepository`/`InMemoryProviderCache`, que deben
compartir estado entre requests.

`get_catalog_unit_of_work` no tiene todavía una implementación real: el
adapter SQLAlchemy de `CatalogUnitOfWork` sigue sin construirse (pendiente
desde el Sprint 2, ver `docs/architecture.md`). Los routers que lo
necesitan (Playback API) quedan completamente implementados y probados
(`tests/integration/playback/`, vía `app.dependency_overrides`), pero para
correr contra datos reales hace falta reemplazar este provider cuando
exista el adapter — no antes.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from geekbaku.application.aggregation.engine import AggregationEngine
from geekbaku.application.aggregation.use_cases.get_aggregated_latest import GetAggregatedLatest
from geekbaku.application.aggregation.use_cases.get_aggregated_popular import (
    GetAggregatedPopular,
)
from geekbaku.application.aggregation.use_cases.search_aggregated_anime import (
    SearchAggregatedAnime,
)
from geekbaku.application.catalog.ports import CatalogUnitOfWork
from geekbaku.application.catalog.use_cases.get_anime_by_id import GetAnimeById
from geekbaku.application.catalog.use_cases.get_anime_episodes import GetAnimeEpisodes
from geekbaku.application.catalog.use_cases.get_catalog_facets import GetCatalogFacets
from geekbaku.application.catalog.use_cases.get_episode_by_id import GetEpisodeById
from geekbaku.application.catalog.use_cases.get_genre import GetGenre
from geekbaku.application.catalog.use_cases.list_catalog import ListCatalog
from geekbaku.application.catalog.use_cases.list_genres import ListGenres
from geekbaku.application.identity.ports import (
    BruteForceGuard,
    IdentityUnitOfWork,
    PasswordHasher,
    TokenService,
)
from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.application.identity.use_cases.get_current_user import GetCurrentUser
from geekbaku.application.identity.use_cases.login_user import LoginUser
from geekbaku.application.identity.use_cases.logout_user import LogoutUser
from geekbaku.application.identity.use_cases.refresh_access_token import RefreshAccessToken
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.application.identity.use_cases.update_profile import UpdateProfile
from geekbaku.application.identity.use_cases.update_settings import UpdateSettings
from geekbaku.application.ingestion.use_cases.ingest_anime_from_provider import (
    IngestAnimeFromProvider,
)
from geekbaku.application.playback.ports import PlaybackSessionRepository
from geekbaku.application.playback.session_store import InMemoryPlaybackSessionRepository
from geekbaku.application.playback.source_resolver import SourceResolver
from geekbaku.application.playback.use_cases.create_session import CreatePlaybackSession
from geekbaku.application.playback.use_cases.get_episode_playback import GetEpisodePlayback
from geekbaku.application.playback.use_cases.get_next_episode import GetNextEpisode
from geekbaku.application.playback.use_cases.get_previous_episode import GetPreviousEpisode
from geekbaku.application.playback.use_cases.get_progress import GetWatchProgress
from geekbaku.application.playback.use_cases.get_qualities import GetAvailableQualities
from geekbaku.application.playback.use_cases.get_resume_point import GetResumePoint
from geekbaku.application.playback.use_cases.get_sources import GetPlaybackSources
from geekbaku.application.playback.use_cases.get_subtitles import GetAvailableSubtitles
from geekbaku.application.playback.use_cases.save_progress import SaveWatchProgress
from geekbaku.application.playback.use_cases.select_quality import SelectPlaybackQuality
from geekbaku.application.playback.use_cases.select_source import SelectPlaybackSource
from geekbaku.application.playback.use_cases.select_subtitle import SelectPlaybackSubtitle
from geekbaku.application.providers.cache import InMemoryProviderCache, ProviderCache
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.application.providers.use_cases.list_providers import ListProviders
from geekbaku.config.settings import get_settings
from geekbaku.domain.identity.value_objects import Identity
from geekbaku.domain.providers.value_objects import (
    CacheConfig,
    ProviderConfiguration,
    ProviderId,
    RateLimitConfig,
    RetryConfig,
)
from geekbaku.infrastructure.catalog.repositories.in_memory_catalog_repository import (
    InMemoryCatalogUnitOfWork,
)
from geekbaku.infrastructure.identity.brute_force_guard import InMemoryBruteForceGuard
from geekbaku.infrastructure.identity.jwt_token_service import JwtTokenService
from geekbaku.infrastructure.identity.password_hasher import Argon2PasswordHasher
from geekbaku.infrastructure.identity.providers.password_provider import (
    PasswordAuthenticationProvider,
)
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from geekbaku.infrastructure.providers.tioanime.adapter import create_tioanime_adapter
from geekbaku.infrastructure.providers.tioanime.client import (
    DEFAULT_BASE_URL as TIOANIME_DEFAULT_BASE_URL,
)


@lru_cache
def get_catalog_unit_of_work() -> CatalogUnitOfWork:
    """Singleton in-memory para todo el proceso — real, no un doble (ver
    `InMemoryCatalogUnitOfWork`). Sin persistencia entre restarts: cuando
    exista el adapter SQLAlchemy (pendiente desde el Sprint 2), reemplaza
    este provider sin tocar ningún caso de uso.
    """
    return InMemoryCatalogUnitOfWork()


@lru_cache
def get_playback_session_repository() -> PlaybackSessionRepository:
    return InMemoryPlaybackSessionRepository()


@lru_cache
def get_playback_metadata_cache() -> ProviderCache:
    return InMemoryProviderCache()


def get_source_resolver() -> SourceResolver:
    return SourceResolver()


def get_episode_playback_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
    resolver: SourceResolver = Depends(get_source_resolver),
    cache: ProviderCache = Depends(get_playback_metadata_cache),
) -> GetEpisodePlayback:
    return GetEpisodePlayback(uow=uow, resolver=resolver, cache=cache)


def get_playback_sources_use_case(
    get_episode_playback: GetEpisodePlayback = Depends(get_episode_playback_use_case),
) -> GetPlaybackSources:
    return GetPlaybackSources(get_episode_playback)


def get_available_qualities_use_case(
    get_episode_playback: GetEpisodePlayback = Depends(get_episode_playback_use_case),
) -> GetAvailableQualities:
    return GetAvailableQualities(get_episode_playback)


def get_available_subtitles_use_case(
    get_episode_playback: GetEpisodePlayback = Depends(get_episode_playback_use_case),
) -> GetAvailableSubtitles:
    return GetAvailableSubtitles(get_episode_playback)


def get_next_episode_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetNextEpisode:
    return GetNextEpisode(uow)


def get_previous_episode_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetPreviousEpisode:
    return GetPreviousEpisode(uow)


def get_create_playback_session_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> CreatePlaybackSession:
    return CreatePlaybackSession(sessions)


def get_select_playback_source_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> SelectPlaybackSource:
    return SelectPlaybackSource(sessions)


def get_select_playback_quality_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> SelectPlaybackQuality:
    return SelectPlaybackQuality(sessions)


def get_select_playback_subtitle_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> SelectPlaybackSubtitle:
    return SelectPlaybackSubtitle(sessions)


def get_save_watch_progress_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> SaveWatchProgress:
    return SaveWatchProgress(sessions)


def get_watch_progress_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> GetWatchProgress:
    return GetWatchProgress(sessions)


def get_resume_point_use_case(
    sessions: PlaybackSessionRepository = Depends(get_playback_session_repository),
) -> GetResumePoint:
    return GetResumePoint(sessions)


# ---------------------------------------------------------------------------
# Catálogo interno (AnimeController, EpisodeController, GenreController,
# CatalogController)
# ---------------------------------------------------------------------------


def get_list_catalog_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> ListCatalog:
    return ListCatalog(uow)


def get_anime_by_id_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetAnimeById:
    return GetAnimeById(uow)


def get_anime_episodes_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetAnimeEpisodes:
    return GetAnimeEpisodes(uow)


def get_episode_by_id_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetEpisodeById:
    return GetEpisodeById(uow)


def get_list_genres_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> ListGenres:
    return ListGenres(uow)


def get_genre_use_case(uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work)) -> GetGenre:
    return GetGenre(uow)


def get_catalog_facets_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
) -> GetCatalogFacets:
    return GetCatalogFacets(uow)


# ---------------------------------------------------------------------------
# Provider Framework / Aggregation Engine (SearchController, ProviderController)
# ---------------------------------------------------------------------------


@lru_cache
def get_provider_manager() -> ProviderManager:
    """Singleton del `ProviderManager` para todo el proceso.

    Registra por defecto el adapter de TioAnime (scraping de
    tioanime.com) — reemplaza a AnimeFLV (Sprint 10) como provider
    wireado por defecto: animeflv.or.at dejó de responder. El adapter de
    AnimeFLV sigue existiendo en el código (`infrastructure/providers/animeflv/`,
    con sus tests), simplemente no se registra acá — mismo tratamiento
    que Jikan. Rate limit deliberadamente conservador (10 req/min): igual
    que con AnimeFLV, tioanime.com es un sitio pensado para navegación
    humana, no una API pensada para consumo programático. Jikan y
    cualquier otro provider siguen sin wireearse automáticamente (ver
    `docs/adding-a-provider.md`).
    """
    manager = ProviderManager()
    tioanime_configuration = ProviderConfiguration(
        provider_id=ProviderId("tioanime"),
        base_url=TIOANIME_DEFAULT_BASE_URL,
        timeout_seconds=10.0,
        rate_limit=RateLimitConfig(max_requests=10, period_seconds=60),
        retry=RetryConfig(max_attempts=2, backoff_base_seconds=1.0),
        cache=CacheConfig(enabled=True, ttl_seconds=300.0),
    )
    manager.register(
        tioanime_configuration.provider_id,
        create_tioanime_adapter(tioanime_configuration),
        priority=10,
        configuration=tioanime_configuration,
    )
    return manager


@lru_cache
def get_aggregation_engine() -> AggregationEngine:
    return AggregationEngine(manager=get_provider_manager())


def get_ingest_anime_from_provider_use_case(
    uow: CatalogUnitOfWork = Depends(get_catalog_unit_of_work),
    manager: ProviderManager = Depends(get_provider_manager),
) -> IngestAnimeFromProvider:
    return IngestAnimeFromProvider(uow, manager)


def get_search_aggregated_anime_use_case(
    engine: AggregationEngine = Depends(get_aggregation_engine),
) -> SearchAggregatedAnime:
    return SearchAggregatedAnime(engine)


def get_aggregated_latest_use_case(
    engine: AggregationEngine = Depends(get_aggregation_engine),
) -> GetAggregatedLatest:
    return GetAggregatedLatest(engine)


def get_aggregated_popular_use_case(
    engine: AggregationEngine = Depends(get_aggregation_engine),
) -> GetAggregatedPopular:
    return GetAggregatedPopular(engine)


def get_list_providers_use_case(
    manager: ProviderManager = Depends(get_provider_manager),
) -> ListProviders:
    return ListProviders(manager)


# ---------------------------------------------------------------------------
# Identity (Sprint 9) — completamente desacoplado de catalog/providers/playback.
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache
def get_identity_unit_of_work() -> IdentityUnitOfWork:
    """Singleton in-memory para todo el proceso — real, no un doble (ver
    `InMemoryIdentityUnitOfWork`), sembrado con roles/permisos base.
    """
    return InMemoryIdentityUnitOfWork()


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_ttl_seconds=settings.jwt_access_token_expire_minutes * 60,
        refresh_token_ttl_seconds=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
    )


@lru_cache
def get_brute_force_guard() -> BruteForceGuard:
    return InMemoryBruteForceGuard()


@lru_cache
def get_authentication_provider_registry() -> AuthenticationProviderRegistry:
    """Reemplazar/agregar una estrategia de autenticación (OAuth,
    magic-link, ...) es registrar otro `AuthenticationProvider` acá —
    ningún caso de uso ni el dominio necesitan cambiar.
    """
    registry = AuthenticationProviderRegistry()
    registry.register(PasswordAuthenticationProvider(get_password_hasher()))
    return registry


def get_register_user_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
    hasher: PasswordHasher = Depends(get_password_hasher),
) -> RegisterUser:
    return RegisterUser(uow, hasher)


def get_login_user_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
    registry: AuthenticationProviderRegistry = Depends(get_authentication_provider_registry),
    tokens: TokenService = Depends(get_token_service),
    guard: BruteForceGuard = Depends(get_brute_force_guard),
) -> LoginUser:
    return LoginUser(uow, registry, tokens, guard)


def get_logout_user_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
    tokens: TokenService = Depends(get_token_service),
) -> LogoutUser:
    return LogoutUser(uow, tokens)


def get_refresh_access_token_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
    tokens: TokenService = Depends(get_token_service),
) -> RefreshAccessToken:
    return RefreshAccessToken(uow, tokens)


def get_current_user_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
) -> GetCurrentUser:
    return GetCurrentUser(uow)


def get_update_profile_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
) -> UpdateProfile:
    return UpdateProfile(uow)


def get_update_settings_use_case(
    uow: IdentityUnitOfWork = Depends(get_identity_unit_of_work),
) -> UpdateSettings:
    return UpdateSettings(uow)


def get_current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    tokens: TokenService = Depends(get_token_service),
) -> Identity:
    """Decodifica el `Authorization: Bearer <token>` a una `Identity`.

    Levanta `AuthenticationError` (401, vía `exception_handlers.py`) si el
    header falta, el esquema no es Bearer, o el token es inválido/expiró —
    `HTTPBearer(auto_error=True)` ya cubre los primeros dos casos.
    """
    return tokens.decode_access_token(credentials.credentials)
