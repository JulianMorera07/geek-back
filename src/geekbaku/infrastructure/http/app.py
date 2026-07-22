from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from geekbaku.config.logging import configure_logging
from geekbaku.config.settings import get_settings
from geekbaku.infrastructure.http.exception_handlers import register_exception_handlers
from geekbaku.infrastructure.http.routers import (
    anime_router,
    auth_router,
    catalog_router,
    episode_router,
    genre_router,
    health_router,
    playback_router,
    provider_router,
    search_router,
)
from geekbaku.infrastructure.identity.security_middleware import (
    AuthRateLimitMiddleware,
    SecurityHeadersMiddleware,
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        description=(
            "API pública de GeekBaku: catálogo interno, búsqueda distribuida entre "
            "providers, reproducción e identidad (JWT + RBAC). Ver `docs/architecture.md`."
        ),
        version="0.1.0",
        debug=settings.debug,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
    )

    # El orden importa: los middlewares se ejecutan en orden inverso al de
    # registro. Rate limit + security headers deben envolver TODO, incluido
    # CORS, así que se agregan últimos.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthRateLimitMiddleware, path_prefix=f"{settings.api_v1_prefix}/auth")
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router.router, prefix=settings.api_v1_prefix)
    app.include_router(anime_router.router, prefix=settings.api_v1_prefix)
    app.include_router(episode_router.router, prefix=settings.api_v1_prefix)
    app.include_router(search_router.router, prefix=settings.api_v1_prefix)
    app.include_router(genre_router.router, prefix=settings.api_v1_prefix)
    app.include_router(catalog_router.router, prefix=settings.api_v1_prefix)
    app.include_router(provider_router.router, prefix=settings.api_v1_prefix)
    app.include_router(playback_router.router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router.router, prefix=settings.api_v1_prefix)

    # Los routers de favoritos/historial/comentarios se registran aquí en
    # sprints siguientes, una vez existan sus casos de uso.

    return app


app = create_app()
