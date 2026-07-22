# GeekBaku Backend

API backend de GeekBaku: agregación de catálogo de streaming, autenticación,
favoritos e historial de reproducción sobre múltiples proveedores de contenido.

> Estado actual: **Sprint 10 completo** (proveedor de scraping activo: **TioAnime**,
> reemplazó a AnimeFLV — ver Sección 23 de `docs/architecture.md`). Dominio y aplicación del catálogo
> (`Anime`, `Season`, `Episode`, `Genre`, `Studio`, `Producer`, `Tag`, ...), el
> **Provider Framework** completo (Registry, Manager, Factory, Configuration,
> Priority, Health/Status, Circuit Breaker, estadísticas, cache con
> invalidación, rate limiting, retry, timeouts, fallback, logging), el
> **primer proveedor real** (Jikan/MyAnimeList, `infrastructure/providers/jikan/`),
> el **segundo proveedor real** (AnimeFLV, scraping HTML con
> BeautifulSoup4+lxml, `infrastructure/providers/animeflv/` — wireado por
> defecto), el **Aggregation Engine** (Deduplication + Ranking + Search
> distribuida + cache agregada sobre múltiples providers), el **Playback
> Engine** (dominio de reproducción, Source Resolver, sesiones/progreso), la
> **API pública** (7 controllers, 12 endpoints `GET` bajo `/api/v1` para
> catálogo, búsqueda agregada, géneros, facetas y estado de proveedores) y el
> **módulo de Identidad** (JWT + Refresh Tokens con rotación y detección de
> reuso, Password Hashing con Argon2id, RBAC con permisos por
> recurso/acción, Authentication Providers pluggable, rate limiting,
> protección de fuerza bruta) están implementados y testeados. Sin
> persistencia real (SQLAlchemy), sin favoritos/historial, sin frontend. Ver
> [`docs/architecture.md`](docs/architecture.md) — en particular la
> [Sección 18](docs/architecture.md#18-sprint-7--playback-engine), la
> [Sección 19](docs/architecture.md#19-sprint-8--api-pública), la
> [Sección 20](docs/architecture.md#20-sprint-9--identity-module) y la
> [Sección 21](docs/architecture.md#21-sprint-10--web-scraping-provider-animeflv)
> — y [`docs/adding-a-provider.md`](docs/adding-a-provider.md) para la guía
> completa de cómo agregar un nuevo proveedor.

## Stack

- Python 3.13 · FastAPI · SQLAlchemy 2 (async) · Alembic
- PostgreSQL · Redis
- Pydantic v2 · JWT
- Docker / docker-compose

## Estructura del proyecto

```
src/geekbaku/
├── domain/
│   ├── catalog/        # Anime, Season, Episode, Genre, Studio, Producer, Tag,
│   │                    # StreamingSource + Value Objects + Domain Services
│   ├── providers/       # StreamingProvider, ProviderHealth, ProviderMetadata, Source,
│   │                    # SearchResult, Catalog, ProviderConfiguration, RateLimitConfig,
│   │                    # RetryConfig, CacheConfig, ProviderStatus
│   ├── playback/         # PlaybackSource, EpisodePlayback, PlaybackSession (Aggregate Root),
│   │                     # WatchProgress, ResumePoint, Subtitle, AudioTrack, StreamingServer
│   ├── identity/          # User (Aggregate Root), Role, Permission, Credential, Session,
│   │                       # RefreshToken, Identity, PasswordPolicy, AuthorizationService
│   └── shared/          # DomainError base
├── application/
│   ├── catalog/         # ports, dto, mappers, use_cases (catálogo interno)
│   ├── providers/       # ProviderPort, ProviderRegistry, ProviderManager, ProviderFactory,
│   │                    # HealthTracker, CircuitBreaker, StatsTracker, RateLimiter,
│   │                    # RetryPolicy, ProviderCache (con invalidación), scheduler (diseño),
│   │                    # dto, normalizers, use_cases, exceptions — el Provider Framework
│   ├── aggregation/     # AggregationEngine, deduplication, ranking, normalization (Images),
│   │                    # AggregationMetrics, dto, use_cases — el Aggregation Engine
│   ├── playback/        # SourceResolver, PlaybackSessionRepository (+ implementación
│   │                    # in-memory), dto, mappers, use_cases — Playback Engine (aplicación)
│   ├── identity/         # AuthenticationProvider/TokenService/PasswordHasher (ports),
│   │                      # AuthenticationProviderRegistry, dto, mappers, loaders,
│   │                      # use_cases — Identity Module (aplicación)
│   ├── search/          # SearchRepository (búsqueda sobre el catálogo interno)
│   └── common/          # Pagination, UnitOfWork genérico
├── infrastructure/
│   ├── providers/
│   │   ├── jikan/        # Primer proveedor real (Jikan/MyAnimeList): client, mapper, adapter
│   │   └── animeflv/     # Segundo proveedor real (scraping HTML): client, mapper, adapter
│   ├── identity/
│   │   ├── jwt_token_service.py       # TokenService — PyJWT
│   │   ├── password_hasher.py          # PasswordHasher — Argon2id
│   │   ├── brute_force_guard.py        # BruteForceGuard en memoria
│   │   ├── security_middleware.py      # SecurityHeadersMiddleware, AuthRateLimitMiddleware
│   │   ├── providers/                  # PasswordAuthenticationProvider (1ra estrategia)
│   │   └── repositories/               # InMemoryIdentityUnitOfWork (real por defecto)
│   └── http/
│       ├── routers/       # anime_, episode_, search_, genre_, catalog_, provider_,
│       │                   # health_, playback_, auth_router.py — API pública + Playback + Identity
│       ├── schemas/       # catalog_, search_, provider_, common_, playback_, identity_schemas.py
│       │                   # (Pydantic, se traducen a/desde los DTOs)
│       └── deps.py        # composition root a nivel de request
├── config/               # Settings (pydantic-settings) y logging
└── composition.py        # Composition root: liga ports a adapters concretos
alembic/                  # Migraciones de base de datos
tests/
├── unit/                 # domain + application + infrastructure (mapper), sin I/O real
├── integration/           # adapter de Jikan, Aggregation Engine multi-provider (respx),
│                           # Playback API, API pública e Identity API (httpx + dependency_overrides)
└── e2e/                   # API completa vía httpx.AsyncClient
```

Ver `docs/architecture.md` para el detalle de capas, módulos, modelo de dominio,
Provider Framework, Aggregation Engine, Playback Engine, Identity Module, casos de uso y
convenciones, y `docs/adding-a-provider.md` para la guía de cómo agregar un nuevo proveedor.

## Requisitos

- Python 3.13+
- Docker y docker-compose (recomendado para levantar Postgres/Redis localmente)

## Setup local

1. Copia el archivo de entorno de ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Instala dependencias (modo editable, con extras de desarrollo):

   ```bash
   pip install -e ".[dev]"
   ```

   Alternativamente, vía `requirements/`:

   ```bash
   pip install -r requirements/dev.txt
   ```

3. Levanta Postgres y Redis:

   ```bash
   docker compose up -d db redis
   ```

4. Ejecuta migraciones (una vez existan modelos ORM, a partir del Sprint 2):

   ```bash
   alembic upgrade head
   ```

5. Levanta la API en modo desarrollo:

   ```bash
   uvicorn geekbaku.infrastructure.http.app:app --reload
   ```

   La documentación OpenAPI queda disponible en `http://localhost:8000/api/v1/docs`, con las
   rutas de catálogo, Playback API e Identity API (`/api/v1/auth/*`) ya navegables sin necesitar
   Postgres: `CatalogUnitOfWork` e `IdentityUnitOfWork` resuelven por defecto a implementaciones
   in-memory reales (`InMemoryCatalogUnitOfWork`/`InMemoryIdentityUnitOfWork`, ver
   `infrastructure/http/deps.py`), no dobles de test — pero ningún dato sobrevive un restart del
   proceso hasta que exista el adapter SQLAlchemy (pendiente desde el Sprint 2). El catálogo
   arranca vacío (`/anime` devuelve `[]`, `/anime/{id}` devuelve `404`) hasta que algo lo
   pueble — hoy no hay un paso de ingesta que persista resultados del Provider Framework como
   `Anime`. Configurá `JWT_SECRET_KEY` en tu `.env` con un
   secreto real de al menos 32 bytes antes de exponer esto fuera de tu máquina.

## Con Docker Compose (stack completo)

```bash
docker compose up --build
```

## Testing

```bash
pytest
```

Los tests de integración de los adapters de Jikan y AnimeFLV (`tests/integration/providers/`)
y del Aggregation Engine multi-provider (`tests/integration/aggregation/`) usan
[`respx`](https://lundberg.github.io/respx/) para interceptar `httpx` a nivel de transporte —
nunca hacen peticiones de red reales (ni a la API de Jikan ni al sitio de AnimeFLV), así que
corren igual de rápido y determinístico que los tests unitarios. Los fixtures HTML de AnimeFLV
son sintéticos (reproducen la estructura del sitio con datos ficticios), no contenido real
scrapeado guardado en el repo.

Los tests de integración de la Playback API (`tests/integration/playback/`), la API pública
(`tests/integration/api/test_public_api.py`) y la Identity API
(`tests/integration/api/test_auth_api.py`) ejercitan la app FastAPI real (`httpx.AsyncClient` +
`ASGITransport`, sin servidor real) inyectando un `CatalogUnitOfWork`/`IdentityUnitOfWork`
in-memory vía `app.dependency_overrides` — el patrón estándar de FastAPI para testear routers
sin depender de infraestructura real. `test_auth_api.py` además fuerza un rebuild de
`app.middleware_stack` en cada test para que `AuthRateLimitMiddleware` (con estado propio, en
memoria, cacheado a nivel de proceso) no arrastre contadores de un test a otro.

## Lint y tipado

```bash
ruff check .
ruff format .
mypy src
```

## Migraciones (Alembic)

```bash
# Generar una migración a partir de cambios en los modelos ORM
alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones pendientes
alembic upgrade head
```

Las migraciones autogeneradas siempre deben revisarse a mano antes de commitear.

## Roadmap de sprints

- **Sprint 1**: esqueleto de proyecto, configuración, FastAPI base, Alembic, Docker.
- **Sprint 2**: dominio + aplicación del catálogo interno (`Anime`, `Season`, `Episode`,
  `Genre`, `Studio`, `Tag`, `StreamingSource`), casos de uso, DTOs, mappers, tests.
- **Sprint 3**: `Producer`, `Rating`, `Thumbnail`/`Banner`/`Trailer`, numeración tipada
  (`SeasonNumber`/`EpisodeNumber`); Provider Engine base (`ProviderPort`, motor de registro y
  despacho, normalización) desacoplado de cualquier proveedor concreto; casos de uso de
  búsqueda/catálogo/últimos/populares/filtrado; `CatalogRepository`, `SearchRepository`,
  `ProviderRepository` (interfaces).
- **Sprint 4**: Data Acquisition Engine completo — `ProviderRegistry` (registro +
  prioridad), `ProviderManager` (orquestación: cache → rate limit → retry → llamada → health →
  logging), `ProviderFactory` (construcción desacoplada de adapters), `ProviderConfiguration`
  (rate limit/retry/cache por provider), `ProviderHealth`/`ProviderStatus` (salud
  operacional), `get_seasons`/`get_related` en `ProviderPort`, normalización de
  temporadas/relaciones/géneros, cache in-memory configurable, rate limiting de ventana fija,
  retry con backoff exponencial, diseño de scheduler (sin cron todavía), logging estructurado.
- **Sprint 5**: Provider Framework endurecido — `CircuitBreaker` (CLOSED/OPEN/
  HALF_OPEN), `StatsTracker` (estadísticas por provider), timeouts aplicados vía
  `asyncio.wait_for`, fallback a "último valor bueno conocido" ante falla/circuito abierto,
  invalidación de cache (`invalidate`/`invalidate_matching`), `ProviderManager.enable`/
  `.disable` dinámico. **Primer proveedor real**: adapter de Jikan/MyAnimeList
  (`infrastructure/providers/jikan/`) implementando las 9 capacidades de `ProviderPort` con
  anti-corrupción real (nunca expone el JSON de Jikan). Sin cambios en `domain/`.
- **Sprint 6**: Aggregation Engine — `AggregationEngine.search`/`get_latest`/
  `get_popular`/`aggregate_detail`, apoyado en `ProviderManager` para todo lo que ya resolvían
  los Sprints 4-5 (paralelismo, prioridad, fallback, timeout/cancelación, métricas, logs).
  Deduplication Engine (`group_search_results`/`group_normalized_anime`, matching por
  external id o similitud de título) + merge que une listas y conserva el registro más
  completo con referencias a todos los providers (`SourceReference`). Ranking Engine
  (prioridad → calidad → completitud → tiempo de respuesta). Normalización ampliada
  (`producers`, `external_ids` en `ProviderAnimeDTO`/`NormalizedAnimeDTO`, validación de
  Images vía `ImageUrl`/`VideoUrl` de dominio). Cache agregada propia con TTL configurable e
  invalidación automática/explícita. `AggregationMetrics`. Sin cambios en `domain/`.
- **Sprint 7**: Playback Engine completo — nuevo `domain/playback/` (`PlaybackSource`,
  `EpisodePlayback`, `PlaybackSession` con máquina de estados, `WatchProgress`/`ResumePoint`
  con reglas de negocio propias, `Subtitle`/`AudioTrack`/`StreamingServer`/`PlaybackProvider`).
  Source Resolver (`SourceSelectionService`: multi-fuente, prioridad, fallback automático,
  múltiples calidades) construido sobre `catalog.Episode.streaming_sources` (Sprint 2). 12
  casos de uso (resolver fuentes, seleccionar calidad/subtítulo, administrar sesiones, guardar
  progreso, navegar episodio siguiente/anterior). **Primeros endpoints HTTP reales del
  proyecto** (`playback_router.py`, 12 rutas) con traducción de errores de dominio a HTTP
  (`NotFoundError`→404, etc.) recién activada en `exception_handlers.py`. Cache de metadata
  reusando `ProviderCache`; progreso nunca cacheado, siempre vía `PlaybackSessionRepository`
  (`InMemoryPlaybackSessionRepository`, implementación real, no un doble).
- **Sprint 8**: API pública — 7 controllers (`AnimeController`, `EpisodeController`,
  `SearchController`, `GenreController`, `CatalogController`, `ProviderController`,
  `HealthController`), 12 endpoints `GET` bajo `/api/v1` (`/anime`, `/anime/{id}`,
  `/anime/{id}/episodes`, `/episodes/{id}`, `/search`, `/latest`, `/popular`, `/genres`,
  `/genres/{id}`, `/catalog`, `/providers`, `/health`). Dos DTOs nuevos (`CatalogFacetsDTO`,
  `ProviderInfoDTO`) y el resto reutilizados de Sprints 2 y 6; Schemas Pydantic espejo 1:1 con
  ejemplos OpenAPI (`Field(examples=[...])`); `PageSchema[T]` (PEP 695) para toda respuesta
  paginada. Casos de uso nuevos delgados (`GetAnimeById`, `GetAnimeEpisodes`,
  `GetEpisodeById`, `GetGenre`, `GetCatalogFacets`, `GetAggregatedLatest`,
  `GetAggregatedPopular`, `ListProviders`) sin lógica de negocio propia. Sin reproducción
  (Playback queda igual que en Sprint 7), sin favoritos, sin historial. Ningún adapter de
  proveedor registrado por defecto — `/search`/`/latest`/`/popular`/`/providers` responden
  vacío hasta que un sprint futuro wiree un adapter concreto.
- **Sprint 9**: Identity Module — nuevo `domain/identity/` completamente desacoplado
  del resto del dominio (`User` Aggregate Root, `Role`, `Permission`, `Credential`, `Session`,
  `RefreshToken`, `Identity` como principal en runtime distinto de `User`, `PasswordPolicy`,
  `AuthorizationService`). Arquitectura de **Authentication Providers** pluggable
  (`AuthenticationProviderRegistry` propio, independiente del `ProviderRegistry` del Provider
  Framework): primera estrategia `PasswordAuthenticationProvider`, agregar una nueva no requiere
  tocar dominio ni casos de uso. **JWT Authentication** (`JwtTokenService`, PyJWT) con
  **Refresh Tokens** que implementan **Token Rotation** y detección de reuso
  (`RefreshToken.rotate`/`RefreshTokenReusedError` — revoca la sesión completa ante un intento
  de reuso). **Password Hashing** con Argon2id (`argon2-cffi`). **RBAC** (`AuthorizationService`,
  permisos `"resource:action"`, policies) con roles base `user`/`admin` sembrados por defecto.
  7 endpoints bajo `/api/v1/auth`: `register`, `login`, `logout`, `refresh`, `me`,
  `PATCH profile`, `PATCH settings`. **Seguridad**: `InMemoryBruteForceGuard` (fuerza bruta por
  `email:ip`), `AuthRateLimitMiddleware` (peticiones por IP en `/auth/*`), `SecurityHeadersMiddleware`
  (headers en toda la app), `PasswordPolicy` (fortaleza mínima). `InMemoryIdentityUnitOfWork`
  real por defecto (no un doble), mismo criterio que `InMemoryPlaybackSessionRepository`. Sin
  cambios en `domain/catalog`, `domain/providers`, `domain/playback` ni en el Provider Framework.
- **Sprint 10 (actual)**: Web Scraping Provider — segundo proveedor real, adapter de AnimeFLV
  (`infrastructure/providers/animeflv/`, scraping de `https://animeflv.or.at/` con
  BeautifulSoup4+lxml, nuevas dependencias) implementando los 9 métodos de `ProviderPort`
  (`search`, `get_anime_detail`, `get_episodes` con fuentes de descarga Mega/MP4Upload/1Fichier,
  `get_seasons`/`get_related`/`get_popular`/`get_genres` con aproximaciones documentadas donde
  el sitio no expone el dato de forma nativa, `get_latest`, `get_types`). Episodios embebidos
  como JSON en la página de detalle (no como enlaces HTML — se renderizan client-side);
  servidores de descarga scrapeados por episodio con concurrencia acotada
  (`asyncio.Semaphore`). **Wireado por defecto** en `deps.get_provider_manager()` con rate limit
  conservador (10 req/min) — a diferencia de Jikan, que sigue sin registrarse automáticamente.
  Tests con fixtures HTML sintéticas (no contenido real scrapeado). Sin cambios en `domain/`
  ni en el Provider Framework (Sprints 3-5). **Hotfix posterior**: `get_catalog_unit_of_work()`
  ya no lanza `NotImplementedError` por defecto (crasheaba `/anime`, `/genres`, `/catalog`, etc.
  al correr `uvicorn --reload` sin overridear la dependencia) — ahora resuelve a
  `InMemoryCatalogUnitOfWork` (`infrastructure/catalog/repositories/`), mismo criterio que
  `InMemoryPlaybackSessionRepository`/`InMemoryIdentityUnitOfWork`: real por defecto, no un
  doble, sin persistencia entre restarts hasta que exista el adapter SQLAlchemy.
  **Segundo hotfix**: nuevo módulo `application/ingestion/` (`IngestAnimeFromProvider`) +
  endpoint `GET /api/v1/anime/external/{provider_id}/{external_id}` — conecta por primera vez
  un resultado de `/search`/`/latest`/`/popular` (provider externo, efímero) con el catálogo
  interno (persistido): ingiere detalle+episodios+fuentes de streaming la primera vez que se
  pide (idempotente en llamadas siguientes), incluyendo mapear las fuentes de descarga
  scrapeadas de AnimeFLV a `Episode.streaming_sources` — con esto, buscar → clickear →
  ver sinopsis/episodios → reproducir vía Playback Engine funciona de punta a punta por
  primera vez. Ver `docs/architecture.md` Sección 22.
  **Tercer hotfix**: animeflv.or.at dejó de responder — se construyó
  `infrastructure/providers/tioanime/` (scraping de `https://tioanime.com/`, mismos 3
  archivos client/mapper/adapter) y se registró en `deps.get_provider_manager()` en lugar
  de AnimeFLV (que sigue en el código, con sus tests, simplemente sin wirear por defecto —
  igual que Jikan). Sitio más simple de scrapear: búsqueda real vía `/api/search` (JSON
  limpio), episodios sin request extra (`var episodes = [...]` embebido + URL derivable
  `/ver/{slug}-{numero}`), fuentes de embed en vez de descarga. **Explícitamente sin
  contenido para adultos**, en dos capas: (1) el sitio de hentai es un dominio
  completamente separado (`tiohentai.com`) que el código nunca referencia — no depende de
  un filtro, depende de que el adapter no sabe que ese dominio existe; (2)
  `mapper.is_adult_genre` descarta defensivamente cualquier género con palabras clave de
  contenido adulto, tanto en la taxonomía pública (`get_genres`) como rechazando el anime
  completo si lo tuviera (`get_anime_detail`). Ver `docs/architecture.md` Sección 23.
- **Sprint 11+ (pendiente)**: adapter SQLAlchemy del catálogo interno y de identidad
  (`CatalogUnitOfWork`/`IdentityUnitOfWork` reales — bloquea que la API pública, la Playback API
  y la Identity API sirvan/persistan datos reales), resolución de los enlaces de descarga de
  AnimeFLV a un stream reproducible directo, ingesta (persistir `AggregatedAnimeDTO` como
  `Anime`), un tercer provider, segunda estrategia de `AuthenticationProvider` (OAuth/OIDC),
  verificación de email, endpoints administrativos de roles/permisos, favoritos, historial,
  comentarios.

## Licencia

Propietario — GeekBaku.
