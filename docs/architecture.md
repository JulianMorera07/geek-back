# GeekBaku Backend — Arquitectura

> Estado: **Aprobada e implementada hasta Sprint 10** (esqueleto de proyecto +
> dominio y aplicación del catálogo + Provider Framework completo + primer
> proveedor real (Jikan) + segundo proveedor real por scraping (AnimeFLV) +
> Aggregation Engine + Playback Engine + API pública para el frontend +
> módulo de Identidad: JWT, RBAC, Authentication Providers). Ver
> [Sección 14](#14-sprint-3--provider-engine-y-estado-real-del-dominio) para
> el Provider Engine base (Sprint 3),
> [Sección 15](#15-sprint-4--data-acquisition-engine) para el Data
> Acquisition Engine (Sprint 4),
> [Sección 16](#16-sprint-5--provider-framework-endurecido-y-primer-proveedor-real)
> para el endurecimiento del framework y el adapter de Jikan (Sprint 5),
> [Sección 17](#17-sprint-6--aggregation-engine) para el Aggregation Engine
> (Sprint 6), [Sección 18](#18-sprint-7--playback-engine) para el Playback
> Engine (Sprint 7: dominio de reproducción, Source Resolver, Playback API,
> primeros endpoints HTTP reales del proyecto),
> [Sección 19](#19-sprint-8--api-pública) para la API pública (Sprint 8: 7
> controllers, 12 endpoints `GET`, DTOs/Schemas consistentes para el
> frontend), [Sección 20](#20-sprint-9--identity-module) para el módulo de
> Identidad (Sprint 9: JWT + Refresh Tokens con rotación, RBAC, Authentication
> Providers pluggable, rate limiting, protección de fuerza bruta), y
> [Sección 21](#21-sprint-10--web-scraping-provider-animeflv) para el adapter
> de AnimeFLV (Sprint 10: segundo proveedor real, basado en scraping HTML en
> vez de una API oficial, wireado por defecto en el `ProviderManager`).
> Todavía sin: persistencia real (SQLAlchemy — el catálogo interno e
> identidad siguen sin un adapter productivo), favoritos, historial,
> frontend.

## 1. Contexto del producto

GeekBaku es una plataforma de **streaming de video/anime** que agrega contenido servido por
**múltiples proveedores externos** (scrapers/APIs de terceros). El backend es responsable de:

- Exponer un catálogo unificado (series, temporadas, episodios) independientemente del proveedor real.
- Resolver, para cada episodio, las fuentes de reproducción disponibles a través de una capa de
  **abstracción de providers**.
- Autenticación y autorización de usuarios.
- Favoritos, historial de reproducción y progreso.
- Búsqueda de catálogo.
- Trabajos en background (sincronización de catálogo con providers, limpieza, etc.).

El frontend **no** es responsabilidad de este backend (ver CLAUDE.md). Este documento cubre
exclusivamente el diseño del backend.

---

## 2. Principios arquitectónicos

- **Clean / Hexagonal Architecture**: el dominio no depende de frameworks, DB ni HTTP.
  Las dependencias siempre apuntan hacia adentro (Dependency Rule).
- **Repository Pattern**: el dominio y los casos de uso hablan con interfaces (`Protocol`/ABC),
  nunca con SQLAlchemy directamente.
- **Dependency Injection**: FastAPI `Depends` + un contenedor explícito de composición
  (`app/composition.py`), sin magia global.
- **DDD ligero**: entidades, value objects, agregados y lenguaje ubicuo donde aporte valor;
  sin sobre-ingeniería (no CQRS/event sourcing salvo que se justifique después).
- **Provider abstraction**: cualquier fuente externa de contenido implementa un puerto común
  (`ContentProviderPort`). Añadir un proveedor nuevo no debe tocar dominio ni casos de uso.
- **Async first**: I/O no bloqueante en toda la cadena (DB, HTTP a providers, Redis).
- **Full typing**: `mypy --strict` (o `pyright` estricto) como objetivo, sin `Any` implícito.

---

## 3. Capas (Hexagonal)

```
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure (adapters)                                    │
│  FastAPI routers · SQLAlchemy repos · Redis · HTTP clients    │
│  Provider adapters · Celery/RQ workers · JWT · Search engine  │
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐  │
│   │  Application (use cases)                                │  │
│   │  Orchestration, DTOs, ports (interfaces), transactions   │  │
│   │                                                           │  │
│   │   ┌───────────────────────────────────────────────┐    │  │
│   │   │  Domain                                          │    │  │
│   │   │  Entities, Value Objects, Aggregates,            │    │  │
│   │   │  Domain services, Domain events, reglas de negocio│   │  │
│   │   └───────────────────────────────────────────────┘    │  │
│   └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

Regla de dependencia: `infrastructure → application → domain`. El dominio no importa nada de
`application` ni `infrastructure`. `application` solo importa `domain` y define **puertos**
(interfaces) que `infrastructure` implementa.

---

## 4. Estructura de carpetas

```
backend/
├── docs/
│   └── architecture.md
├── src/
│   └── geekbaku/
│       ├── domain/
│       │   ├── catalog/
│       │   │   ├── entities.py          # Series, Season, Episode
│       │   │   ├── value_objects.py     # Slug, Duration, Rating, ProviderRef
│       │   │   ├── events.py            # SeriesPublished, EpisodeAdded...
│       │   │   └── exceptions.py
│       │   ├── user/
│       │   │   ├── entities.py          # User
│       │   │   ├── value_objects.py     # Email, PasswordHash, Username
│       │   │   └── exceptions.py
│       │   ├── favorites/
│       │   │   └── entities.py          # FavoriteItem
│       │   ├── history/
│       │   │   └── entities.py          # PlaybackProgress, WatchEvent
│       │   ├── providers/
│       │   │   ├── entities.py          # Provider, ProviderSource
│       │   │   └── value_objects.py     # StreamQuality, PlaybackUrl
│       │   └── shared/
│       │       ├── value_objects.py     # EntityId, Pagination
│       │       └── errors.py            # DomainError base
│       │
│       ├── application/
│       │   ├── catalog/
│       │   │   ├── use_cases/
│       │   │   │   ├── list_catalog.py
│       │   │   │   ├── get_series_detail.py
│       │   │   │   ├── get_episode_sources.py
│       │   │   │   └── sync_catalog_from_providers.py
│       │   │   ├── ports.py             # SeriesRepository, EpisodeRepository
│       │   │   └── dto.py
│       │   ├── auth/
│       │   │   ├── use_cases/
│       │   │   │   ├── register_user.py
│       │   │   │   ├── login_user.py
│       │   │   │   ├── refresh_token.py
│       │   │   │   └── logout_user.py
│       │   │   ├── ports.py             # UserRepository, TokenService, PasswordHasher
│       │   │   └── dto.py
│       │   ├── favorites/
│       │   │   ├── use_cases/
│       │   │   │   ├── add_favorite.py
│       │   │   │   ├── remove_favorite.py
│       │   │   │   └── list_favorites.py
│       │   │   └── ports.py
│       │   ├── history/
│       │   │   ├── use_cases/
│       │   │   │   ├── record_progress.py
│       │   │   │   ├── get_continue_watching.py
│       │   │   │   └── list_history.py
│       │   │   └── ports.py
│       │   ├── search/
│       │   │   ├── use_cases/
│       │   │   │   └── search_catalog.py
│       │   │   └── ports.py             # SearchIndexPort
│       │   ├── providers/
│       │   │   ├── ports.py             # ContentProviderPort (puerto único)
│       │   │   └── registry.py          # ProviderRegistry (resuelve provider por id)
│       │   └── common/
│       │       ├── unit_of_work.py      # UnitOfWork port
│       │       └── pagination.py
│       │
│       ├── infrastructure/
│       │   ├── db/
│       │   │   ├── base.py              # Declarative base, session factory
│       │   │   ├── models/              # SQLAlchemy ORM models (separados del dominio)
│       │   │   │   ├── catalog.py
│       │   │   │   ├── user.py
│       │   │   │   ├── favorites.py
│       │   │   │   └── history.py
│       │   │   ├── repositories/        # Implementaciones de los ports
│       │   │   │   ├── sqlalchemy_series_repository.py
│       │   │   │   ├── sqlalchemy_user_repository.py
│       │   │   │   ├── sqlalchemy_favorites_repository.py
│       │   │   │   └── sqlalchemy_history_repository.py
│       │   │   └── unit_of_work.py      # SqlAlchemyUnitOfWork
│       │   ├── cache/
│       │   │   └── redis_client.py
│       │   ├── auth/
│       │   │   ├── jwt_token_service.py
│       │   │   └── passlib_hasher.py
│       │   ├── providers/
│       │   │   ├── base.py              # BaseProviderAdapter (implementa ContentProviderPort)
│       │   │   ├── provider_a/
│       │   │   │   └── adapter.py
│       │   │   ├── provider_b/
│       │   │   │   └── adapter.py
│       │   │   └── registry.py          # Wiring concreto de providers habilitados
│       │   ├── search/
│       │   │   └── postgres_fulltext_search.py  # o meilisearch/opensearch adapter
│       │   ├── background/
│       │   │   ├── celery_app.py
│       │   │   └── tasks/
│       │   │       └── sync_catalog_task.py
│       │   └── http/
│       │       ├── app.py               # FastAPI app factory
│       │       ├── deps.py              # Depends() providers (composition root de request)
│       │       ├── middlewares.py
│       │       ├── exception_handlers.py
│       │       └── routers/
│       │           ├── auth_router.py
│       │           ├── catalog_router.py
│       │           ├── favorites_router.py
│       │           ├── history_router.py
│       │           └── search_router.py
│       │       └── schemas/             # Pydantic request/response models (NO dominio)
│       │           ├── auth_schemas.py
│       │           ├── catalog_schemas.py
│       │           ├── favorites_schemas.py
│       │           └── history_schemas.py
│       │
│       ├── config/
│       │   ├── settings.py              # Pydantic Settings (env vars)
│       │   └── logging.py
│       │
│       └── composition.py               # Composition root: instancia adapters y los liga a ports
│
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   ├── integration/
│   │   ├── repositories/
│   │   └── providers/
│   └── e2e/
│       └── api/
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

**Notas clave:**

- `domain/` no importa `sqlalchemy`, `fastapi` ni `pydantic`. Los Value Objects pueden usar
  `dataclasses(frozen=True)` puros.
- Los modelos SQLAlchemy (`infrastructure/db/models`) son **distintos** de las entidades de
  dominio. Los repositorios traducen entre ambos (mapper explícito, sin herencia compartida).
- Los schemas Pydantic de FastAPI (`infrastructure/http/schemas`) son distintos de los DTOs de
  `application`. Los routers traducen `Schema → DTO → UseCase → DTO → Schema`.
- `composition.py` es el único lugar que sabe "qué implementación concreta de cada puerto se usa".
  Los routers reciben instancias ya resueltas vía `Depends`.

---

## 5. Módulos (bounded contexts ligeros)

| Módulo | Responsabilidad |
|---|---|
| **auth** | Registro, login, refresh, logout, gestión de contraseñas, emisión/validación de JWT |
| **catalog** | Series, temporadas, episodios; sincronización con providers; detalle de catálogo |
| **providers** | Puerto único `ContentProviderPort` + adaptadores concretos por proveedor externo |
| **favorites** | Marcar/desmarcar favoritos, listar favoritos del usuario |
| **history** | Progreso de reproducción, "continuar viendo", historial completo |
| **search** | Búsqueda de catálogo por texto (título, género, etc.) |

Cada módulo tiene su propio `domain/<módulo>`, `application/<módulo>` y, cuando aplica,
`infrastructure/.../<módulo>`. Los módulos se comunican entre sí **solo a través de casos de uso
o eventos de dominio**, nunca importando repositorios de otro módulo directamente.

---

## 6. Modelo de dominio

### 6.1 Catalog

```
Series (Aggregate Root)
 ├─ id: SeriesId
 ├─ title: str
 ├─ slug: Slug
 ├─ synopsis: str
 ├─ genres: list[Genre]
 ├─ status: SeriesStatus (ONGOING | COMPLETED | ANNOUNCED)
 ├─ cover_url: str
 └─ seasons: list[Season]

Season (Entity, hijo de Series)
 ├─ id: SeasonId
 ├─ number: int
 └─ episodes: list[Episode]

Episode (Entity, hijo de Season)
 ├─ id: EpisodeId
 ├─ number: int
 ├─ title: str
 ├─ duration: Duration (VO)
 └─ provider_refs: list[ProviderRef]   # qué providers tienen este episodio

ProviderRef (Value Object)
 ├─ provider_id: ProviderId
 └─ external_id: str                   # id del contenido en el proveedor externo
```

### 6.2 Providers

```
ContentSource (Value Object, NO persistido — resuelto en tiempo real)
 ├─ provider_id: ProviderId
 ├─ quality: StreamQuality (SD | HD | FHD | UHD)
 ├─ playback_url: PlaybackUrl
 └─ expires_at: datetime | None        # si el link es firmado/temporal
```

`ContentSource` se resuelve on-demand (no se persiste en DB) porque las URLs de los
proveedores externos suelen expirar. Se puede cachear en Redis con TTL corto.

### 6.3 User

```
User (Aggregate Root)
 ├─ id: UserId
 ├─ email: Email (VO, valida formato)
 ├─ username: Username (VO)
 ├─ password_hash: PasswordHash (VO, nunca expone el plano)
 ├─ role: UserRole (USER | ADMIN)
 ├─ is_active: bool
 └─ created_at: datetime
```

### 6.4 Favorites

```
FavoriteItem (Entity)
 ├─ id: FavoriteId
 ├─ user_id: UserId
 ├─ series_id: SeriesId
 └─ added_at: datetime
```

### 6.5 History

```
PlaybackProgress (Aggregate Root — uno por user+episode)
 ├─ id: PlaybackProgressId
 ├─ user_id: UserId
 ├─ episode_id: EpisodeId
 ├─ position_seconds: int
 ├─ duration_seconds: int
 ├─ completed: bool                    # derivado: position/duration >= umbral
 └─ updated_at: datetime
```

`WatchEvent` (histórico append-only, opcional) se puede añadir después si se necesita
analítica; no se incluye en el MVP para evitar sobre-diseño.

### 6.6 Invariantes de dominio relevantes

- Un `Episode` no puede existir sin al menos un `ProviderRef`.
- `PlaybackProgress.position_seconds` nunca puede exceder `duration_seconds`.
- `Series.status` solo transiciona `ANNOUNCED → ONGOING → COMPLETED` (no hacia atrás).
- `FavoriteItem` es único por `(user_id, series_id)` — invariante reforzada en el dominio
  y con constraint único en DB como defensa en profundidad.

---

## 7. Casos de uso (application layer)

### Auth
- `RegisterUser` — valida email único, hashea password, crea `User`.
- `LoginUser` — verifica credenciales, emite access + refresh token.
- `RefreshToken` — rota refresh token, emite nuevo access token.
- `LogoutUser` — invalida refresh token (blacklist en Redis).

### Catalog
- `ListCatalog` — listado paginado/filtrado (género, status).
- `GetSeriesDetail` — serie + temporadas + episodios.
- `GetEpisodeSources` — resuelve `ContentSource[]` para un episodio vía `ProviderRegistry`,
  con fallback si un provider falla (circuit breaker simple) y caché corta en Redis.
- `SyncCatalogFromProviders` — job programado: consulta cada provider habilitado, hace
  upsert de `Series/Season/Episode` en el catálogo interno.

### Favorites
- `AddFavorite`, `RemoveFavorite`, `ListFavorites`.

### History
- `RecordProgress` — upsert de `PlaybackProgress` (llamado periódicamente por el player).
- `GetContinueWatching` — últimos episodios no completados, ordenados por `updated_at`.
- `ListHistory` — historial completo paginado.

### Search
- `SearchCatalog` — búsqueda por texto libre sobre título/sinopsis/género.

Cada caso de uso es una clase con un único método público (`execute`/`__call__`), recibe sus
dependencias (ports) por constructor, y no conoce FastAPI ni SQLAlchemy.

---

## 8. Estrategia de autenticación

- **JWT** (access + refresh, asimétrico con `RS256` recomendado sobre `HS256` para poder
  rotar claves y, si hace falta, validar en otros servicios sin compartir secreto simétrico).
- **Access token**: vida corta (15 min), va en `Authorization: Bearer`.
- **Refresh token**: vida larga (7–30 días), rotación en cada uso (refresh token reuse
  detection → si un refresh ya usado se reintenta, se revocan todos los tokens del usuario).
- **Almacenamiento de refresh tokens**: hash del token en Redis (o tabla `refresh_tokens`),
  no el token en claro. Permite revocación (logout, logout-all-devices).
- **Password hashing**: `argon2` (vía `passlib` o `argon2-cffi`) en lugar de bcrypt puro,
  por mejor resistencia a GPU cracking.
- **Autorización**: RBAC simple (`USER`, `ADMIN`) vía dependency `require_role(...)` en
  FastAPI. Si se necesita granularidad futura (permisos por recurso), se añade sin romper
  la interfaz de los use cases.
- **Rate limiting** en `login`/`register` (Redis + slowapi o middleware propio) para mitigar
  fuerza bruta.

---

## 9. Estrategia de persistencia

- **PostgreSQL** como store principal (catálogo, usuarios, favoritos, historial).
- **SQLAlchemy 2.0** en modo async (`AsyncSession`, `asyncpg` driver).
- **Alembic** para migraciones; una migración por cambio de esquema, revisada a mano
  (no autogenerate ciego).
- **Unit of Work pattern**: cada caso de uso que escribe en más de un repositorio lo hace
  dentro de un único `UnitOfWork` (transacción atómica), inyectado como puerto.
- **Repository pattern**: un repositorio por agregado (`SeriesRepository`, `UserRepository`,
  `FavoriteRepository`, `PlaybackProgressRepository`). Sin repositorios genéricos tipo
  `GenericRepository[T]` — cada uno expone métodos con significado de dominio
  (`get_by_slug`, `find_active_by_email`, etc.), no CRUD genérico.
- **Redis**:
  - Cache de resolución de `ContentSource` (TTL corto, acorde a expiración real del link).
  - Blacklist/whitelist de refresh tokens.
  - Rate limiting.
  - Cola de tareas (si se usa Celery con Redis como broker) o Redis Streams para jobs simples.
- **Búsqueda**: MVP con `tsvector`/full-text search de PostgreSQL (sin infra adicional).
  Si el catálogo crece o se necesita fuzzy/typo-tolerant search, se migra a un
  `SearchIndexPort` respaldado por Meilisearch/OpenSearch sin tocar casos de uso.
- **Migraciones de datos de providers**: el resultado de `SyncCatalogFromProviders` se
  persiste como upsert idempotente, keyed por `(provider_id, external_id)`.

---

## 10. Convenciones

### Código
- `snake_case` para funciones/variables, `PascalCase` para clases, `SCREAMING_SNAKE_CASE`
  para constantes.
- Un caso de uso = un archivo = una clase con método `execute`.
- Los ports son `Protocol` (PEP 544) en vez de ABC cuando no se necesita lógica compartida.
- Nada de imports de `infrastructure` dentro de `domain` o `application` (se refuerza con
  `import-linter` o regla de `ruff`/CI).
- Excepciones de dominio heredan de `DomainError`; se traducen a `HTTPException` únicamente
  en la capa `infrastructure/http` (un `exception_handlers.py` centralizado, nunca
  `try/except HTTPException` dentro de un caso de uso).

### API
- Prefijo de versión: `/api/v1/...`.
- Recursos en plural, kebab/snake consistente: `/api/v1/series`, `/api/v1/episodes/{id}/sources`.
- Paginación: `?page=&page_size=`, respuesta con `items`, `total`, `page`, `page_size`.
- Errores: formato uniforme `{ "error": { "code": "...", "message": "..." } }`, con códigos
  de dominio estables (no solo el mensaje humano) para que el frontend pueda mapear.
- Todos los endpoints documentados vía OpenAPI (docstrings + `response_model` explícito,
  nunca `dict` como response type).

### Testing
- **Unit tests**: dominio y casos de uso, con fakes/in-memory de los ports (sin DB real).
- **Integration tests**: repositorios contra Postgres real (testcontainers o DB de test
  dockerizada), adaptadores de providers contra mocks HTTP (`respx`/`httpx` mock).
- **E2E tests**: FastAPI `TestClient`/`httpx.AsyncClient` contra la app completa con DB de test.
- Cobertura objetivo: dominio y casos de uso cerca del 100%; infraestructura, lo pragmático.

### Git / calidad
- `ruff` (lint + format), `mypy` en CI, pre-commit hooks.
- Commits atómicos por caso de uso o adapter, no por capa transversal.

---

## 11. APIs principales (v1)

### Auth
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/auth/register` | Registro de usuario |
| POST | `/api/v1/auth/login` | Login, devuelve access+refresh |
| POST | `/api/v1/auth/refresh` | Rota refresh token |
| POST | `/api/v1/auth/logout` | Revoca refresh token actual |

### Catalog
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/series` | Listado paginado/filtrado |
| GET | `/api/v1/series/{slug}` | Detalle con temporadas/episodios |
| GET | `/api/v1/episodes/{id}/sources` | Fuentes de reproducción (resuelve providers) |

### Search
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/search?q=` | Búsqueda de catálogo |

### Favorites (auth requerida)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/favorites` | Listar favoritos del usuario |
| POST | `/api/v1/favorites/{series_id}` | Añadir a favoritos |
| DELETE | `/api/v1/favorites/{series_id}` | Quitar de favoritos |

### History (auth requerida)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/history/progress` | Reportar progreso de reproducción |
| GET | `/api/v1/history/continue-watching` | "Continuar viendo" |
| GET | `/api/v1/history` | Historial completo paginado |

### Admin (rol ADMIN, opcional en MVP)
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/admin/catalog/sync` | Dispara sincronización manual con providers |

---

## 12. Decisiones abiertas (a confirmar antes de implementar)

1. **JWT**: ¿`RS256` con rotación de claves, o `HS256` simétrico para simplificar el MVP?
2. **Búsqueda**: ¿Postgres full-text alcanza para el volumen esperado o se arranca ya con
   Meilisearch?
3. **Background jobs**: ¿Celery+Redis, RQ, o `arq` (async-native, más simple con FastAPI)?
4. **Providers concretos**: nombres/contratos reales de los proveedores a integrar, para
   definir bien el `ContentProviderPort` (rate limits, autenticación por provider, formato
   de respuesta).
5. **Multiidioma/subtítulos**: ¿entra en el modelo de `Episode` desde el MVP o se pospone?

---

## 13. Próximos pasos

Una vez aprobada esta arquitectura:
1. Definir contratos exactos de `ContentProviderPort` con al menos un provider real de referencia.
2. Generar el esqueleto de carpetas y `pyproject.toml`.
3. Implementar `domain` + `application` de `auth` y `catalog` primero (son la base del resto).
4. Migraciones iniciales de Alembic.
5. Adapters de infraestructura + routers.

---

## 14. Sprint 3 — Provider Engine y estado real del dominio

Esta sección documenta lo que **realmente existe en el código** tras los Sprints 2 y 3, en
`domain/catalog`, `domain/providers`, `application/catalog`, `application/providers` y
`application/search`. Nada de esto toca `infrastructure/` (sin SQLAlchemy real todavía), ni
autenticación, ni reproducción, ni un provider concreto: solo dominio + aplicación + abstracción.

### 14.1 Dos catálogos, deliberadamente separados

El diseño distingue dos fuentes de verdad que **no se mezclan**:

| | Catálogo interno (`domain/catalog`) | Motor de providers (`domain/providers`) |
|---|---|---|
| Qué es | Nuestros propios datos, persistidos, curados | Datos en vivo de sitios externos, no persistidos |
| Confiabilidad | Confiable (ya validado contra nuestras reglas) | No confiable hasta normalizar |
| Repositorios | `AnimeRepository`, `EpisodeRepository`, `GenreRepository`, `StudioRepository`, `ProducerRepository`, `TagRepository`, `CatalogRepository` | `ProviderRepository` (solo config de qué providers existen) |
| Acceso en runtime | A través de `CatalogUnitOfWork` | A través del `ProviderEngine` (no es un repositorio: no persiste) |
| Devuelve | Entidades de dominio (`Anime`, `Episode`, ...) | DTOs (`ProviderAnimeDTO`, `SearchResultDTO`, ...) — ver 14.3 |

Un provider **sirve** contenido de catálogo; nunca al revés. Por eso `domain/providers` puede
importar de `domain/catalog` (reutiliza `Language`, `AnimeType`, `StreamQuality`, `Thumbnail`),
pero `domain/catalog` no conoce `domain/providers`.

### 14.2 Modelo de dominio del catálogo (`domain/catalog`)

```
Anime (Aggregate Root)
 ├─ id, title, slug, type (AnimeType), status (AnimeStatus)
 ├─ synopsis, country (Country), rating (Rating | None)
 ├─ genre_ids / studio_ids / producer_ids / tag_ids   (referencias, no embeds)
 ├─ media: list[Media]  →  thumbnail / banner / trailer se DERIVAN de acá (properties)
 ├─ external_ids: list[ExternalId]     (MAL, AniList, TMDB... — metadata externa)
 ├─ relations: list[Relation]          (SEQUEL, PREQUEL, SPIN_OFF...)
 └─ seasons: list[Season]
     └─ episodes: list[Episode]
         ├─ media, external_ids
         └─ streaming_sources: list[StreamingSource]   (persistido, con provider_name/external_ref)

Genre / Studio / Producer / Tag   → Aggregate Roots simples, catálogos abiertos, con repo propio
```

**Por qué `Studio` y `Producer` son entidades distintas**: `Studio` es quien anima la obra;
`Producer` es la empresa que la financia/licencia (comité de producción). Ambos son catálogos
abiertos independientes, cada Anime referencia varios de cada uno.

**Por qué `Thumbnail`/`Banner`/`Trailer` no son campos separados en `Anime`**: `Anime` sigue
guardando una única lista `media: list[Media]` (kind + url) como en el Sprint 2. `Thumbnail`,
`Banner` y `Trailer` son Value Objects que envuelven `ImageUrl`/`VideoUrl` y se exponen como
propiedades computadas (`Anime.thumbnail`, `.banner`, `.trailer`) que buscan el primer `Media`
del `kind` correspondiente. Un único storage, vocabulario de dominio expresivo hacia afuera.

**Numeración tipada**: `Season.number` y `Episode.number` son `SeasonNumber`/`EpisodeNumber`
(Value Objects que validan > 0), no `int` crudo — evita pasar un número de temporada donde se
espera un número de episodio por error de tipos.

**`Rating`**: puntuación agregada (`score` 0–10, `votes`, `source`) que un `Anime` puede tener
0 o 1 vez por ahora (`Anime.set_rating`). Pensado para admitir múltiples ratings por fuente
("internal", "mal", "anilist") en un sprint futuro sin romper la API actual.

**`ExternalId` vs `ExternalReference`**: son conceptos distintos a propósito.
- `ExternalId` (`domain/catalog`) vincula un `Anime`/`Episode` **nuestro** con un catálogo de
  metadata externo (MAL, AniList, TMDB) para enriquecimiento — no sirve para reproducir nada.
- `ExternalReference` (`domain/providers`) identifica contenido **dentro de un provider de
  streaming concreto** (`provider_id` + `external_id`); es la clave que el `ProviderEngine` usa
  para pedirle detalle/episodios a ESE provider.

### 14.3 Provider Engine (`application/providers`)

El corazón de este sprint. Objetivo: agregar N proveedores de streaming detrás de una única
interfaz, sin que el dominio ni los casos de uso conozcan ninguno en particular.

```
                    ┌─────────────────────────────┐
                    │        ProviderEngine         │   registro (dict[ProviderId, ProviderPort])
                    │  register() / unregister()    │   + despacho + agregación resiliente
                    └───────────────┬───────────────┘
                                    │  implementa
                     ┌──────────────┴──────────────┐
                     │         ProviderPort          │  ← LA interfaz única (Protocol)
                     │  search / get_anime_detail /   │
                     │  get_episodes / get_latest /   │
                     │  get_popular / get_genres /    │
                     │  get_types                     │
                     └──────────────┬──────────────┘
                ┌────────────────────┼────────────────────┐
        (futuro) ProviderA      (futuro) ProviderB     (futuro) ProviderC
        adapter concreto        adapter concreto       adapter concreto
        (fuera de alcance       (fuera de alcance      (fuera de alcance
         de este sprint)         de este sprint)        de este sprint)
```

**Agregar/quitar un provider** es `engine.register(provider_id, instancia)` /
`engine.unregister(provider_id)` desde el composition root — cero cambios en dominio o casos de
uso. No implementado en este sprint: ningún adapter concreto (`provider_a`, `provider_b`, ...),
tal como se pidió ("no implementes scraping específico para un proveedor").

**DTOs, no entidades, en el borde de providers**: `ProviderPort` devuelve
`ProviderAnimeDTO`/`ProviderEpisodeDTO`/`SearchResultDTO` (primitivos, `application/providers/dto.py`),
no entidades de dominio. Es deliberado: un proveedor externo es una fuente **no confiable**
todavía — antes de convertirse en algo con la forma de nuestro dominio, tiene que pasar por
`application/providers/normalizers.py`. Comparar con `AnimeRepository` (nuestro propio store,
confiable), que sí devuelve entidades de dominio directamente.

**Resiliencia del `ProviderEngine`**:
- Operaciones que consultan **un solo** provider (`get_anime_detail`, `get_episodes`,
  `get_catalog`) propagan cualquier falla envuelta en `ProviderRequestError` — no hay nada que
  agregar, así que no tiene sentido ocultar el error.
- Operaciones que consultan **varios** providers a la vez (`search`, `get_latest`,
  `get_popular`) usan `asyncio.gather(..., return_exceptions=True)`: si UN provider falla, se
  omite del resultado agregado y los demás igual responden. Está probado explícitamente en
  `tests/unit/application/providers/test_engine.py::TestFanOut`.

**Normalización** (`application/providers/normalizers.py`): cada provider describe tipo/estado
con su propio vocabulario libre (ej. `"Currently Airing"`, `"TV Series"`). `normalize_type` y
`normalize_status` traducen por coincidencia de palabras clave a `AnimeType`/`AnimeStatus`; ante
un valor no reconocido, caen a un default documentado (`AnimeType.TV` / `AnimeStatus.ANNOUNCED`)
en vez de fallar — un campo con formato inesperado de UN provider no debe tumbar toda una
búsqueda agregada. `slugify` genera un slug cuando el provider no trae uno propio.

### 14.4 Casos de uso añadidos en Sprint 3

**Catálogo interno** (`application/catalog/use_cases`, además de los del Sprint 2):
`CreateProducer`, `ListProducers`.

**Provider Engine** (`application/providers/use_cases`), un 1:1 con las capacidades del motor:

| Caso de uso | Capacidad del Engine |
|---|---|
| `SearchAnime` | Search |
| `GetProviderAnimeDetail` | Anime Detail (+ normalización) |
| `GetProviderEpisodes` | Episodes (+ normalización) |
| `GetProviderCatalog` | Genres + Types combinados |
| `GetLatest` | Latest |
| `GetPopular` | Popular |
| `FilterSearchResults` | Filtrado en memoria sobre resultados ya obtenidos (no todo provider soporta filtros finos en su propia API) |
| `NormalizeAnime` | Expone explícitamente la capa anti-corrupción, reutilizable fuera de un fetch del Engine |

### 14.5 Repository Interfaces (resumen completo tras Sprint 3)

| Puerto | Módulo | Devuelve | Implementado en este sprint |
|---|---|---|---|
| `AnimeRepository` | `application/catalog/ports.py` | `Anime` | Interfaz (adapter SQLAlchemy pendiente) |
| `EpisodeRepository` | `application/catalog/ports.py` | `Episode` | Interfaz |
| `GenreRepository` / `StudioRepository` / `ProducerRepository` / `TagRepository` | `application/catalog/ports.py` | `Genre`/`Studio`/`Producer`/`Tag` | Interfaz |
| `CatalogRepository` | `application/catalog/ports.py` | `Anime` (últimos, populares) | Interfaz — sin caso de uso propio todavía (`list_popular` depende de métricas de un módulo `history` que no existe aún) |
| `SearchRepository` | `application/search/ports.py` | `AnimeId` | Interfaz — búsqueda full-text sobre el catálogo interno, distinta de `ProviderPort.search` (externo) |
| `ProviderRepository` | `application/providers/ports.py` | `StreamingProvider` | Interfaz — persistiría qué providers están habilitados; el registro en memoria del `ProviderRegistry` no depende de esto todavía (ver Sección 15) |

`CatalogRepository`, `SearchRepository` y `ProviderRepository` se definen ahora (piezas
explícitamente pedidas) pero no tienen todavía un caso de uso propio que las consuma: quedan
como contratos listos para que un sprint futuro implemente el adapter sin re-diseñar nada.

### 14.6 Qué faltaba tras Sprint 3 (retomado en Sprint 4)

- Adapters concretos de `ProviderPort` (scraping/HTTP real de un proveedor) — **sigue sin
  implementarse** (fuera de alcance también en Sprint 4).
- Registro/priorización/salud de providers formalizados — **resuelto en Sprint 4**, ver abajo.
- Cache, rate limiting, retry, logging estructurado — **resuelto en Sprint 4**, ver abajo.
- Adapters SQLAlchemy de todos los repositorios (`infrastructure/db/repositories`) — pendiente.
- Ingesta: persistir un `NormalizedAnimeDTO` como `Anime` real — pendiente.
- Autenticación, reproducción, frontend — explícitamente excluidos, siguen pendientes.

---

## 15. Sprint 4 — Data Acquisition Engine

Sprint 4 formaliza y completa el Provider Engine del Sprint 3 en un **Data Acquisition
Engine**: el subsistema responsable de obtener datos de proveedores externos de forma
desacoplada, resiliente y observable. Vive enteramente en `application/providers/` +
`domain/providers/`; no toca `infrastructure/`, autenticación, reproducción ni un proveedor
concreto.

### 15.1 De `ProviderEngine` a `ProviderRegistry` + `ProviderManager`

El Sprint 3 tenía una única clase (`ProviderEngine`) que registraba providers y despachaba
llamadas. Sprint 4 separa esa responsabilidad en dos piezas con un propósito único cada una:

```
ProviderFactory                 ProviderRegistry                 ProviderManager
(construye adapters              (almacena qué providers          (orquesta CADA llamada:
 a partir de una                  existen, habilitados,            cache → rate limit →
 ProviderConfiguration,            en qué prioridad;                retry → llamada real →
 sin acoplarse a ninguna           agrupa adapter +                 health tracking →
 clase concreta)                  StreamingProvider +               logging)
                                  ProviderConfiguration)
                                        │
                                        ▼
                                 ProviderRegistration
                            (adapter, provider, configuration)
```

`ProviderManager.register(provider_id, adapter, ...)` mantiene la misma firma que
`ProviderEngine.register` del Sprint 3 (compatibilidad hacia atrás): internamente delega en
`ProviderRegistry`, que construye el `StreamingProvider` (prioridad, habilitado) asociado.

### 15.2 Provider Interface ampliada

`ProviderPort` (`application/providers/ports.py`) — la interfaz única que todo proveedor debe
implementar — gana dos capacidades nuevas pedidas por Data Acquisition:

- `get_seasons(reference) -> list[ProviderSeasonDTO]` (Obtener temporadas)
- `get_related(reference) -> list[ProviderRelatedDTO]` (Obtener información relacionada)

Junto con las ya existentes (`search`, `get_anime_detail`, `get_episodes`, `get_latest`,
`get_popular`, `get_genres`, `get_types`), cubre las 8 capacidades de adquisición pedidas.

### 15.3 Provider Configuration, Priority, Health y Status

- **`ProviderConfiguration`** (`domain/providers/value_objects.py`): configuración operacional
  de UN provider — `base_url`, `timeout_seconds`, `rate_limit` (`RateLimitConfig | None`),
  `retry` (`RetryConfig`), `cache` (`CacheConfig`). Se asocia a un registro vía
  `ProviderRegistry.register(..., configuration=...)`. Distinta de `StreamingProvider`
  (config **administrativa**: habilitado/prioridad, ya existía en Sprint 3) — una es "cómo se
  comporta técnicamente", la otra es "si lo usamos y con qué preferencia".
- **`Provider Priority`**: `StreamingProvider.priority` (int, ya existía) ahora se usa
  activamente: `ProviderRegistry.list_enabled_by_priority()` ordena de mayor a menor prioridad,
  y `ProviderManager` fan-out (`search`/`get_latest`/`get_popular`) recorre los providers en
  ese orden cuando no se especifican `provider_ids` explícitos.
- **`ProviderHealth`** (`domain/providers/entities.py`, entidad de dominio): `status`
  (`ProviderStatus`: `UNKNOWN` → `DEGRADED` tras la 1ª falla → `DOWN` tras 3 fallas
  consecutivas por default; cualquier éxito vuelve a `HEALTHY` y resetea el contador).
  `HealthTracker` (`application/providers/health.py`) lleva un `ProviderHealth` por provider y
  lo actualiza en cada llamada real hecha por el Manager.
- **Uso de Health**: solo afecta la **selección** de providers en operaciones agregadas (un
  provider `DOWN` se excluye de `search`/`get_latest`/`get_popular` cuando no se piden
  providers explícitos) — nunca bloquea una llamada dirigida a un provider específico
  (`get_anime_detail`, `get_episodes`, ...): ahí el llamador pidió expresamente ESE provider.

### 15.4 Normalización ampliada

Se agregan a `application/providers/normalizers.py`:
- `normalize_relation_type` (+ `to_normalized_related`): igual patrón que `normalize_type`/
  `normalize_status` (palabras clave, default `RelationType.OTHER`) para el vocabulario de
  relaciones narrativas de cada provider ("Sequel", "Side Story", ...).
- `to_normalized_season`: temporada cruda → `NormalizedSeasonDTO`.
- `normalize_genre_names`: limpia (espacios, duplicados) nombres de género crudos,
  preservando el orden. **No** los resuelve contra `GenreRepository` (eso es matching/creación
  de una futura capa de ingesta, fuera de alcance): el objetivo aquí es solo que el string ya
  esté limpio, no vincularlo a un `Genre` propio con id.

Se mantiene el principio del Sprint 3: **nunca se expone un modelo propio del proveedor** —
todo lo que sale de `ProviderManager` hacia un caso de uso pasa por un DTO `Normalized*` antes
de llegar al consumidor (excepto las operaciones de solo-lectura que ya son agregados
neutrales, como `SearchResultDTO`/`ProviderCatalogDTO`, que no tienen vocabulario propio de un
provider que traducir).

### 15.5 Cache

`application/providers/cache.py`: puerto `ProviderCache` (`get`/`set` genérico con TTL) +
`InMemoryProviderCache` (implementación de referencia, un solo proceso). El `ProviderManager`
cachea toda operación de lectura (todas excepto ninguna: `get_anime_detail`, `get_episodes`,
`get_seasons`, `get_related`, `get_genres`, `get_types`, `search`, `get_latest`, `get_popular`),
con clave determinística (`build_cache_key`: operación + provider + argumentos relevantes) y
TTL configurable **por provider** vía `ProviderConfiguration.cache` (`enabled`, `ttl_seconds`).
Sin `cache=` al construir el `ProviderManager`, el cacheo queda deshabilitado globalmente (el
comportamiento por default es no cachear, para no sorprender a quien no lo configure).
Reemplazar `InMemoryProviderCache` por un adapter Redis (para compartir cache entre réplicas
del backend) es un cambio de infraestructura futuro que no toca al Manager.

### 15.6 Rate Limiting

`application/providers/rate_limiter.py`: `RateLimiter` de ventana fija, con un contador
independiente por `ProviderId`. Cada provider define su propio límite vía
`ProviderConfiguration.rate_limit` (`RateLimitConfig`: `max_requests`, `period_seconds`); sin
`rate_limit` configurado, no hay límite. Al excederse, `ProviderManager` lanza
`ProviderRateLimitExceededError` **antes** de intentar la llamada real (no hace la petición ni
cuenta como falla de salud). El reloj es inyectable para tests determinísticos.

### 15.7 Retry Policy

`application/providers/retry.py`: `RetryPolicy.run` reintenta una operación async hasta
`RetryConfig.max_attempts` veces, con backoff exponencial
(`backoff_base_seconds * backoff_multiplier ** intento`). Cada provider define su propia
política vía `ProviderConfiguration.retry`; sin configuración, aplica el default
(`max_attempts=3`, `backoff_base_seconds=0.5`, `backoff_multiplier=2.0`). La función de espera
es inyectable (`sleep`), así los tests no dependen de tiempo real.

### 15.8 Scheduler (diseño, sin cron)

`application/providers/scheduler.py` define la FORMA de una sincronización periódica sin
ejecutar ninguna:
- `SyncJobDefinition`: `provider_id` + `operation` (una de `latest`/`popular`/`genres`/`types`
  — las operaciones que tiene sentido sincronizar periódicamente, no las dirigidas a un
  contenido puntual) + `interval_seconds` + `enabled`.
- `SyncSchedulerPort`: puerto para un futuro scheduler real (cron/APScheduler/Celery Beat) —
  **sin implementación** este sprint.
- `InMemorySyncJobRegistry`: registro en memoria de `SyncJobDefinition`, solo para
  describir/inspeccionar/testear la configuración deseada — no dispara ninguna llamada.

Cuando un sprint futuro implemente `SyncSchedulerPort` de verdad, la pieza que ejecuta cada
job llamará al `ProviderManager` (ej. `get_latest`) y pasará el resultado a la (todavía
inexistente) capa de ingesta del catálogo interno.

### 15.9 Logging

`ProviderManager` usa `logging.getLogger("geekbaku.providers")` (integra con
`config/logging.py` sin configuración adicional) y registra, en cada llamada real:

| Evento | Nivel | Cuándo |
|---|---|---|
| `provider_call_succeeded` | INFO | Llamada exitosa — incluye provider, operación, tiempo de respuesta (`elapsed_ms`) |
| `provider_retry` | WARNING | Antes de cada reintento — incluye número de intento y error |
| `provider_call_failed` | ERROR | Falla final tras agotar reintentos — incluye tiempo total y cantidad de reintentos |
| `provider_rate_limited` | WARNING | Rate limit excedido, la llamada real no se hizo |
| `provider_cache_hit` | DEBUG | La respuesta vino de cache, no se llamó al provider |

### 15.10 Casos de uso añadidos en Sprint 4

| Caso de uso | Capacidad de adquisición |
|---|---|
| `GetProviderSeasons` | Obtener temporadas |
| `GetProviderRelated` | Obtener información relacionada |
| `GetProviderGenres` | Obtener géneros (dedicado; `GetProviderCatalog` los sigue combinando con tipos) |

Los casos de uso del Sprint 3 (`SearchAnime`, `GetProviderAnimeDetail`, `GetProviderEpisodes`,
`GetProviderCatalog`, `GetLatest`, `GetPopular`, `FilterSearchResults`, `NormalizeAnime`) se
mantienen sin cambios en su interfaz pública, solo actualizan su dependencia de
`ProviderEngine` a `ProviderManager`.

### 15.11 Qué faltaba tras Sprint 4 (retomado/resuelto en Sprint 5)

- Adapters concretos de `ProviderPort` — **resuelto en Sprint 5** (Jikan).
- Circuit breaker, fallback, timeout, invalidación de cache, estadísticas — **resueltos en
  Sprint 5**.
- Adapter Redis para `ProviderCache` (solo existe `InMemoryProviderCache`) — pendiente.
- Implementación real de `SyncSchedulerPort` (cron/APScheduler/Celery Beat) — solo diseño,
  sigue pendiente (fuera de alcance también en Sprint 5).
- Ingesta: conectar `NormalizedAnimeDTO`/`NormalizedEpisodeDTO` con `CreateAnime`/`AddEpisode`
  del catálogo interno — pendiente.
- Autenticación, reproducción (Playback Engine), frontend — explícitamente excluidos, pendientes.

---

## 16. Sprint 5 — Provider Framework endurecido y primer proveedor real

Sprint 5 tenía dos objetivos posibles y mutuamente excluyentes en el pedido original (uno
pedía "Playback Engine", el otro "no desarrolles reproducción" + Provider Framework); se
resolvió con el usuario que **Sprint 5 = Provider Framework + primer proveedor real**. El
Playback Engine queda para un sprint futuro. Restricción explícita de este sprint: **no se
modificó nada bajo `domain/`** — todo lo nuevo vive en `application/providers/` e
`infrastructure/providers/`.

### 16.1 Qué ya existía (Sprint 4) vs. qué se agregó (Sprint 5)

| Pieza pedida | Estado antes de Sprint 5 | Qué se agregó en Sprint 5 |
|---|---|---|
| Sistema de adapters (`ProviderPort`) | Ya existía | Sin cambios (ya cumplía "misma interfaz para todos") |
| `ProviderManager` (registrar múltiples) | Ya existía | Wiring de circuit breaker/stats/fallback/timeout |
| `ProviderFactory` | Ya existía | Sin cambios |
| Sistema de prioridades | Ya existía (`StreamingProvider.priority`) | Sin cambios |
| Health Check | Ya existía (`ProviderHealth`/`HealthTracker`) | Sin cambios |
| Deshabilitar dinámicamente | Ya existía (`ProviderRegistry.enable/disable`) | `ProviderManager.enable`/`.disable` (conveniencia) |
| **Sistema de estadísticas** | No existía | **Nuevo**: `ProviderStats` + `StatsTracker` |
| **Circuit Breaker** | No existía (Sprint 4 documentaba explícitamente que Health NO bloqueaba llamadas) | **Nuevo**: `CircuitBreaker` |
| **Timeouts** | `ProviderConfiguration.timeout_seconds` existía pero no se usaba | **Nuevo**: aplicado en cada intento vía `asyncio.wait_for` |
| **Fallback** | No existía | **Nuevo**: último valor bueno conocido, servido ante falla/circuit abierto |
| **Invalidación de cache** | Solo `clear()` (todo o nada) | **Nuevo**: `invalidate`/`invalidate_matching`, expuestos por Manager |
| **Primer adapter real** | No existía | **Nuevo**: `infrastructure/providers/jikan/` |

### 16.2 Por qué algunas piezas nuevas NO están en `domain/`

`ProviderCircuitOpenError` vive en `application/providers/exceptions.py` (no en
`domain/providers/exceptions.py`, donde está el resto de las excepciones de providers) y
`CircuitBreakerConfig` vive en `application/providers/circuit_breaker.py` (no como VO en
`domain/providers/value_objects.py`, donde sí están `RateLimitConfig`/`RetryConfig`/
`CacheConfig`, conceptualmente hermanas). Esto es una **inconsistencia deliberada**, no un
descuido: la restricción explícita de este sprint era no tocar el dominio. Un sprint futuro
que revisite `domain/providers` podría reconciliar la ubicación de toda esta familia de
configuración/excepciones en un único lugar.

### 16.3 `ProviderManager._dispatch`: pipeline completo

Con Sprint 5, cada llamada a un provider específico atraviesa, en orden:

```
1. Cache (¿hit? → devolver, fin)
2. Circuit Breaker (¿OPEN? → intentar Fallback; si no hay, ProviderCircuitOpenError)
3. Rate Limiter (¿excedido? → ProviderRateLimitExceededError, sin llamar)
4. Retry × Timeout (cada intento: asyncio.wait_for(llamada_real, timeout))
   4a. Éxito → Health=HEALTHY, Circuit=CLOSED, Stats++, cachea, guarda "último bueno"
   4b. Falla final → Health=falla, Circuit=falla, Stats++, intenta Fallback;
       si no hay, ProviderRequestError
5. Logging en cada etapa (provider, operación, tiempo de respuesta, reintentos, errores)
```

`HealthTracker` y `CircuitBreaker` se actualizan en paralelo pero tienen roles distintos
(ver docstring de `circuit_breaker.py`): Health es observabilidad para ORDENAR/excluir
providers de un fan-out agregado (`search`/`get_latest`/`get_popular`); Circuit Breaker es
protección activa que corta incluso una llamada DIRIGIDA a un provider específico
(`get_anime_detail`, etc.) mientras está `OPEN`.

### 16.4 Circuit Breaker

`application/providers/circuit_breaker.py`: máquina de estados de 3 pasos por provider —
`CLOSED` (normal) → `OPEN` tras `failure_threshold` fallas consecutivas (default 5, más alto
que el umbral de `HealthTracker` para `DOWN` —3— a propósito, para no solaparse con los tests
de Health del Sprint 4) → `HALF_OPEN` tras `cooldown_seconds` (default 30s) → un éxito en
`HALF_OPEN` cierra el circuito, una falla lo reabre y reinicia el cooldown.

### 16.5 Fallback

Estrategia "stale-on-error": en cada llamada de solo-lectura exitosa (todas menos ninguna:
detalle, episodios, temporadas, relacionados, géneros, tipos, búsqueda/últimos/populares por
provider), `ProviderManager` guarda el resultado en un store interno de "último valor bueno"
(`_last_good`, independiente del TTL del cache — no expira). Si una llamada posterior falla
definitivamente (retries agotados) o el circuit breaker está `OPEN`, se sirve ese último valor
conocido en vez de propagar el error (con log `provider_fallback_used` en WARNING y contador
en `ProviderStats.fallback_used_calls`). Desactivable globalmente con
`ProviderManager(enable_fallback=False)`.

### 16.6 Timeouts

`ProviderConfiguration.timeout_seconds` (ya existía desde Sprint 4, sin uso) ahora envuelve
cada intento individual dentro de `RetryPolicy` vía `asyncio.wait_for` — un timeout cuenta como
una falla más, sujeta a reintento igual que cualquier otra excepción. El adapter de Jikan
además configura su propio `httpx.AsyncClient(timeout=...)` con el mismo valor: doble
protección, documentada como intencional.

### 16.7 Sistema de estadísticas

`application/providers/stats.py`: `ProviderStats` por provider — `total_calls`,
`successful_calls`, `failed_calls`, `retried_calls`, `rate_limited_calls`,
`circuit_rejected_calls`, `cache_hits`/`cache_misses`, `fallback_used_calls`,
`average_response_time_ms`, `success_rate`, `last_call_at`, `last_error`. Puramente
observacional (no cambia el comportamiento del Manager). Accesible vía
`manager.get_stats(provider_id)` / `manager.get_all_stats()`.

### 16.8 Cache: invalidación

`ProviderCache.invalidate(key)` (una clave exacta) e `invalidate_matching(predicate)`
(cualquier criterio, ej. "todo lo de este provider"). `ProviderManager` expone
`invalidate_cache(operation, provider_id, *parts)` e `invalidate_provider_cache(provider_id)`
como conveniencia. Se sigue cacheando **únicamente información no específica de usuario**
(igual que en Sprint 4): nada de progreso de reproducción ni cualquier dato por-usuario pasa
por este cache.

### 16.9 Primer proveedor real: Jikan (MyAnimeList)

`infrastructure/providers/jikan/` — adapter contra la API pública de Jikan v4
(`https://api.jikan.moe/v4`, sin autenticación):

| Capacidad de `ProviderPort` | Endpoint de Jikan usado | Nota |
|---|---|---|
| `search` | `GET /anime?q=...` | — |
| `get_anime_detail` | `GET /anime/{id}/full` | `404` → `None` (no se trata como falla transitoria) |
| `get_episodes` | `GET /anime/{id}/episodes` | `external_id` del episodio = `"{anime_id}:{episode_id}"` |
| `get_seasons` | `GET /anime/{id}/full` | Jikan no modela temporadas por anime (cada cour es una entrada MAL separada); se deriva 1 `ProviderSeasonDTO` con el conteo total de episodios — documentado como aproximación pragmática |
| `get_related` | `GET /anime/{id}/relations` | Se descartan entries que no son de tipo "anime" (manga, etc.) |
| `get_latest` | `GET /seasons/now` | Anime en emisión actual, usado como proxy de "últimos" |
| `get_popular` | `GET /top/anime` | Ranking de MAL |
| `get_genres` | `GET /genres/anime` | — |
| `get_types` | *(sin endpoint)* | Lista estática (`STATIC_ANIME_TYPES`): Jikan no expone un catálogo de tipos separado |

`country_code` se asume siempre `"JP"` (MAL es un catálogo de anime japonés); no hay concepto
de "banner" distinto del cover en Jikan, así que `banner_url` queda `None`. `tags` combina
"themes" + "demographics" de MAL (más cercano al concepto de `Tag` libre que al de `Genre`).

**Anti-corrupción real**: en ningún método de `JikanProviderAdapter` se devuelve el `dict` que
llega de `JikanClient` — todo pasa por `mapper.py` antes de salir. `mapper.py` no tiene ninguna
dependencia de `httpx` ni de I/O: son funciones puras, testeadas con fixtures (`test_mapper.py`)
sin red real.

**Resiliencia del adapter**: `JikanProviderAdapter` no implementa retry, timeout, cache ni
circuit breaker por su cuenta — todo eso lo aplica `ProviderManager` de forma genérica (ver
16.3), exactamente igual que para cualquier otro provider. Es la prueba de que el Provider
Framework realmente desacopla la resiliencia del adapter concreto.

### 16.10 Tests

- `tests/unit/infrastructure/providers/jikan/test_mapper.py`: unit tests puros del mapper
  (fixtures de JSON crudo, sin HTTP).
- `tests/integration/providers/jikan/test_adapter.py`: integración con `respx` (mockea
  `httpx` a nivel de transporte, sin red real), un test por capacidad de `ProviderPort` más
  casos de error (404, 500).
- `tests/integration/providers/jikan/test_manager_integration.py`: extremo a extremo —
  `ProviderFactory` construye el adapter, se registra en un `ProviderManager` real (no un
  doble), se ejercitan cache hit y retry-tras-falla-transitoria con HTTP mockeado.
- `tests/unit/application/providers/test_circuit_breaker.py`, `test_stats.py`: nuevas piezas
  aisladas.
- `tests/unit/application/providers/test_manager.py`: extendido con timeout, circuit breaker,
  fallback, enable/disable dinámico, estadísticas, invalidación de cache — sin romper ningún
  test existente del Sprint 4 (se corrió la suite completa antes y después de cada cambio).

### 16.11 Qué faltaba tras Sprint 5 (retomado en Sprint 6)

- Playback Engine — sigue pospuesto (fuera de alcance también en Sprint 6).
- Autenticación, frontend — siguen pendientes.
- Un segundo proveedor real (probar más de un adapter simultáneo en producción) — sigue
  pendiente; Sprint 6 sí ejercita **dos** providers a la vez en sus tests (Jikan real +
  `FakeProviderPort`), pero eso es un test, no un segundo adapter de producción.
- Ingesta: persistir lo que trae un provider como `Anime`/`Episode` reales del catálogo
  interno — sigue pendiente.
- "Consultar varios providers y devolver una única respuesta normalizada" — **resuelto en
  Sprint 6** (Aggregation Engine).
- Endpoints HTTP (routers) — no se pidió tampoco en Sprint 6.

---

## 17. Sprint 6 — Aggregation Engine

Sprint 6 agrega una capa nueva, `application/aggregation/`, que se apoya en TODO lo construido
en Sprints 3-5 (`ProviderManager`, Provider Framework) sin modificar `domain/` en ningún
archivo. Objetivo: consultar múltiples providers y devolver una única respuesta normalizada,
deduplicada y ordenada.

### 17.1 Decisión de diseño central: reusar, no reinventar

El pedido de "AGGREGATION ENGINE" lista 8 capacidades: múltiples proveedores, prioridades,
fallback automático, consultas paralelas, timeouts, cancelación de proveedores lentos,
métricas, logs. **6 de las 8 ya existían en `ProviderManager` desde los Sprints 4 y 5** (fan-out
paralelo vía `asyncio.gather`, orden por prioridad, fallback a último valor bueno conocido,
timeout vía `asyncio.wait_for` — que cancela la tarea al vencer —, `StatsTracker`/`HealthTracker`,
logging estructurado). `AggregationEngine` NO las reimplementa: llama a
`ProviderManager.search`/`get_latest`/`get_popular` (que ya hacen todo eso) y agrega, sobre el
resultado, lo genuinamente nuevo de este sprint: **Deduplication Engine** y **Ranking Engine**,
más una cache/métricas propias del nivel agregado (distintas de las por-provider).

```
AggregationEngine.search(query, pagination, provider_ids)
        │
        ▼
ProviderManager.search(...)   ← YA hace: fan-out paralelo, prioridad, fallback,
        │                        timeout/cancelación, circuit breaker, rate limit,
        │                        cache por-provider, retry, stats, logs (Sprints 4-5)
        ▼
list[SearchResultDTO]  (de varios providers, sin deduplicar)
        │
        ▼
deduplication.group_search_results()   ← NUEVO: agrupa por similitud de título/tipo
        │
        ▼
deduplication.merge_search_results()   ← NUEVO: fusiona cada grupo en 1 registro,
        │                                 con SourceReference hacia cada provider
        ▼
ranking.rank_search_results()          ← NUEVO: ordena por prioridad → calidad →
        │                                 completitud → tiempo de respuesta
        ▼
list[AggregatedSearchResultDTO]  (cacheado a nivel agregado antes de devolver)
```

### 17.2 Normalization Engine: qué es nuevo y qué se reusa

`application/providers/normalizers.py` (Sprint 3+) ya normalizaba Anime, Episode, Season,
Relation, tipo/estado. Sprint 6 completa la lista pedida (Producer, Rating, Images, External
IDs) con cambios puntuales, no destructivos:

- **`ProviderAnimeDTO`/`NormalizedAnimeDTO`** (`application/providers/dto.py`) ganan dos campos
  nuevos con default vacío (`producers`, `external_ids`) — compatibles hacia atrás, ningún test
  existente de Sprint 3-5 se rompió al agregarlos (se corrió la suite completa antes/después).
- **Producer**: se normaliza igual que género/estudio (`normalize_genre_names`, reusada — pese
  al nombre, es genérica: limpia espacios y duplicados de cualquier lista de nombres libres).
- **External IDs**: nuevo `normalize_external_id_source` (mismo patrón best-effort por palabras
  clave que `normalize_type`/`normalize_status`, default `ExternalIdSource.OTHER`) +
  `normalize_external_ids` (limpia y dedupe). El adapter de Jikan ahora se autoreferencia
  (`[("mal", "16498")]`) y reporta su array `producers` (distinto de `studios` en la API real).
- **Rating**: ya se normalizaba (`rating_score`, Sprint 3); Sprint 6 lo usa además como señal de
  `quality_score` en el Ranking Engine (17.4).
- **Images**: `application/aggregation/normalization.py` (nuevo) — `normalize_image_url`/
  `normalize_video_url` validan contra los Value Objects de dominio `ImageUrl`/`VideoUrl`
  (**usarlos no modifica el dominio**, solo se importan) antes de aceptar una URL en un
  resultado agregado; una URL rota de un provider se descarta silenciosamente en vez de colarse.

### 17.3 Deduplication Engine

`application/aggregation/deduplication.py`. Estrategia de matching, en orden de confianza:

1. **External ID compartido** (ej. ambos providers reportan `mal:16498`) → match seguro. Solo
   aplica al detalle completo (`NormalizedAnimeDTO`, que sí trae `external_ids` desde Sprint 6);
   `SearchResultDTO` no los tiene, así que a nivel de búsqueda cae al criterio 2.
2. **Mismo tipo + título "suficientemente similar"** (`titles_are_similar`: normaliza
   mayúsculas/espacios/puntuación y compara con `difflib.SequenceMatcher`, umbral 0.88) → match
   heurístico.

`group_search_results`/`group_normalized_anime` agrupan con un algoritmo greedy O(n²) (aceptable:
los conjuntos a deduplicar son del tamaño de una página de resultados, no todo el catálogo).
`merge_search_results`/`merge_normalized_anime` fusionan cada grupo:
- Campo por campo, se prefiere el valor del provider de **mayor prioridad** que lo tenga; si ese
  provider no lo reportó, se toma el primero disponible entre los demás ("conserva el registro
  más completo" sin descartar lo que solo un provider secundario sabía).
- Listas (`genres`/`studios`/`producers`/`tags`/`external_ids`) se **unen** (unión sin
  duplicados), no se sobrescriben.
- `rating_score` se promedia entre los providers que lo reportan.
- `sources: tuple[SourceReference, ...]` mantiene una referencia hacia **cada** provider
  contribuyente, nunca solo hacia el "ganador" — así un consumidor puede, por ejemplo, pedir el
  detalle completo a cada uno de esos providers después (`aggregate_detail`, 17.5).

### 17.4 Ranking Engine

`application/aggregation/ranking.py`. Orden **lexicográfico** estricto (cada criterio solo
desempata cuando el anterior queda igual), en el orden pedido:

1. Prioridad máxima entre los providers contribuyentes.
2. `quality_score` — `rating_score / 10` normalizado a 0-1; sin rating, score neutral (0.5).
3. `completeness_score` — fracción de campos relevantes presentes (10 campos para detalle:
   sinopsis/thumbnail/banner/trailer/rating/genres/studios/producers/tags/external_ids; 3 para
   resultados de búsqueda: thumbnail/tipo/año).
4. Tiempo de respuesta — el más rápido entre los providers contribuyentes gana (lee
   `ProviderStats.average_response_time_ms` del Sprint 5, sin recalcular nada).

`rank_*` es la única forma "oficial" de obtener estos scores: `deduplication.merge_*` los deja
en `0.0` a propósito, para que el cálculo de calidad viva en un único lugar.

### 17.5 Detalle agregado (fusión completa, no solo de búsqueda)

`AggregationEngine.aggregate_detail(references)` recibe una lista de `ExternalReferenceDTO` —
una por provider — que YA se sabe que corresponden al mismo anime (ej. tomadas de
`AggregatedSearchResultDTO.sources` tras una búsqueda). Pide el detalle a cada provider en
paralelo (`asyncio.gather`, con aislamiento de fallas: si un provider falla o no tiene el
anime, se ignora y se fusiona con los que sí respondieron — `None` solo si todos fallan) y
fusiona con la misma lógica de `merge_normalized_anime` que agrupa por external_id/título. Cada
llamada individual a `ProviderManager.get_anime_detail` sigue pasando por todo el pipeline de
resiliencia del Sprint 5 (cache, circuit breaker, retry, timeout, health, stats) sin que este
método tenga que preocuparse por nada de eso.

### 17.6 Search Engine (búsqueda distribuida)

Es el flujo end-to-end descrito en 17.1, expuesto como caso de uso:
`SearchAggregatedAnime.execute(query, page, page_size, provider_ids)` →
`list[AggregatedSearchResultDTO]`. El usuario busca una vez; el sistema consulta N providers en
paralelo; el Aggregation Engine devuelve una sola lista, deduplicada y ordenada.

### 17.7 Cache de resultados agregados

Reusa el mismo `ProviderCache`/`InMemoryProviderCache` del Sprint 5
(`application/providers/cache.py` — es un cache genérico de clave/valor con TTL, no algo
específico de "por-provider"), pero con una **instancia separada** de la que usa
`ProviderManager` internamente: invalidar la cache del Aggregation Engine no toca la cache
por-provider, y viceversa. TTL configurable por `AggregationEngine(cache_ttl_seconds=...)`
(default 300s). Invalidación:
- **Automática**: expiración por TTL, igual que la cache por-provider.
- **Explícita**: `invalidate_search_cache(query, pagination, provider_ids)` (una entrada) e
  `invalidate_all_cache()` (todo lo que produjo este engine).

### 17.8 Métricas y logs

`application/aggregation/metrics.py`: `AggregationMetrics` — `total_aggregations`,
`total_raw_results`, `total_merged_results`, `total_duplicates_merged`, `cache_hits`/
`cache_misses`, más las propiedades derivadas `average_raw_results_per_aggregation`,
`deduplication_rate`, `cache_hit_rate`. Es el equivalente, a nivel de agregación, de
`ProviderStats` (Sprint 5, que es por-provider) — ambos coexisten sin pisarse.

Logs bajo `logging.getLogger("geekbaku.aggregation")` (namespace propio, distinto de
`"geekbaku.providers"`): `aggregation_search_completed`/`aggregation_get_latest_completed`/
`aggregation_get_popular_completed` (INFO, con query/raw/merged/elapsed_ms),
`aggregation_detail_completed` (INFO), `aggregation_detail_fetch_failed` (WARNING, por
provider aislado), `aggregation_cache_hit` (DEBUG).

### 17.9 Tests

- `tests/unit/application/aggregation/`: `test_normalization.py`, `test_deduplication.py`,
  `test_ranking.py`, `test_metrics.py` (piezas aisladas), `test_engine.py` (integra Provider
  Framework real + `FakeProviderPort` — múltiples providers registrados en un
  `ProviderManager` real, verificando dedup/merge/rank/cache/metrics end-to-end),
  `test_use_cases.py`.
- `tests/integration/aggregation/test_multi_provider_aggregation.py`: el adapter **real** de
  Jikan (HTTP mockeado con `respx`, sin red) registrado JUNTO a un `FakeProviderPort` en el
  mismo `ProviderManager` — prueba el caso concreto que motiva este sprint: dos providers
  DISTINTOS reportando el mismo anime, deduplicados en un único resultado agregado que combina
  campos de ambos.

### 17.10 Qué faltaba tras Sprint 6 (retomado en Sprint 7)

- Playback Engine — **resuelto en Sprint 7**.
- Endpoints HTTP — **Sprint 7 los introduce, pero solo para Playback** (búsqueda/detalle
  agregados del Aggregation Engine siguen sin exponerse por HTTP).
- Autenticación, frontend — siguen excluidos.
- Un segundo adapter de producción real (Sprint 6 solo prueba multi-provider en tests).
- Ingesta: persistir un `AggregatedAnimeDTO` como `Anime` real del catálogo interno.
- Resolución de `genres`/`studios`/`producers` normalizados contra los repositorios propios
  (`GenreRepository`, etc.) — siguen siendo strings libres, no ids de nuestro catálogo.

---

## 18. Sprint 7 — Playback Engine

Sprint 7 construye el subsistema responsable de TODA la experiencia de reproducción: qué
fuentes existen para un episodio, cuál elegir, qué calidad/subtítulo usar, cómo administrar
una sesión de reproducción y su progreso, y cómo navegar entre episodios. Es también el primer
sprint que expone **endpoints HTTP reales** (`infrastructure/http/routers/playback_router.py`) —
hasta ahora todo el trabajo vivía en `domain/`/`application/`, sin infraestructura HTTP viva.

### 18.1 Un nuevo dominio: `domain/playback/`

A diferencia de los Sprints 5-6 (que prohibían tocar el dominio), Sprint 7 no tenía esa
restricción, así que el Playback Engine tiene su propio módulo de dominio, simétrico a
`domain/catalog` y `domain/providers`:

```
domain/playback/
├── value_objects.py   # PlaybackSessionId, PlaybackSourceId, PlaybackSessionStatus,
│                       # SubtitleFormat, SubtitleUrl, Subtitle, AudioTrack,
│                       # StreamingServer, PlaybackProvider, PlaybackMetadata,
│                       # WatchProgress, ResumePoint
├── entities.py         # PlaybackSource, EpisodePlayback, PlaybackSession (Aggregate Root)
├── services.py         # SourceSelectionService, ResumePointService
└── exceptions.py
```

Reutiliza vocabulario ya existente en vez de duplicarlo: `StreamQuality` y `Language`
(`domain.catalog`) son exactamente el mismo concepto para reproducción que para catálogo, así
que `PlaybackSource.quality`/`AudioTrack.language` los importan directo — no existe un
`VideoQuality` nuevo y paralelo.

**Sesiones anónimas, a propósito.** Sin autenticación todavía, `PlaybackSession` no tiene
`user_id`: se identifica y se recupera solo por su propio `PlaybackSessionId`. Guardar/leer
progreso no necesita saber "de quién" es, solo "de qué sesión". Cuando exista autenticación, un
sprint futuro puede agregar la asociación usuario↔sesión sin romper este modelo.

**`Subtitle.url` es opcional.** Modela dos casos reales: `url=None` significa "hardsub" (el
subtítulo está grabado en el video de un `PlaybackSource` específico — común en releases de un
solo archivo); con `url`, es un softsub real, seleccionable independientemente de la fuente de
video. `catalog.StreamingSource.subtitle_language` (Sprint 2) mapea al primer caso: no hay un
archivo de subtítulos separado en ese modelo, solo la señal de que ese source ya trae subs en
ese idioma.

**`ResumePointService`** aplica una regla de negocio real, no solo devuelve la última posición
guardada: progreso ≥95% de la duración se trata como completado (reanudar reinicia desde 0, no
"reanuda" 3 segundos antes del final); progreso ≤2% se descarta por insignificante. Entre
medio, reanuda exactamente donde quedó.

### 18.2 Source Resolver

`application/playback/source_resolver.py`. Deliberadamente sin I/O ni cache propios: recibe un
`Anime`/`Season`/`Episode` YA cargados y arma un `EpisodePlayback` (metadata + fuentes
candidatas), delegando la selección en `SourceSelectionService` (dominio puro).

**De dónde salen las fuentes — y su límite honesto.** `catalog.Episode.streaming_sources`
(persistido desde el Sprint 2) es el puente entre catálogo y reproducción: cada
`StreamingSource` ya tiene `provider_name`/`external_ref`/`quality`/idiomas, y opcionalmente
una `url` ya resuelta. `to_playback_source` (mapper) solo puede convertir a `PlaybackSource`
reproducible las entradas que **ya tienen `url`** — las que no, se omiten. Resolver
dinámicamente una URL fresca contra un provider en vivo requeriría un método en `ProviderPort`
que no existe todavía (`ProviderPort` nunca tuvo una capacidad de "obtener URL de
reproducción", intencionalmente fuera de alcance desde el Sprint 3). Esto es una limitación
real y documentada, no un descuido: la selección/priorización/fallback SÍ está completamente
implementada sobre lo que ya está persistido.

**Multi-fuente, prioridad, fallback, múltiples calidades** — los 4 requisitos del Source
Resolver — viven en `SourceSelectionService.rank` (dominio):
1. Excluye fuentes inactivas/vencidas (`PlaybackSource.is_available`).
2. Ordena por: ¿coincide con la calidad preferida? → prioridad explícita de provider (lista
   dada) → prioridad propia del provider → mejor calidad. Si ninguna fuente coincide con la
   calidad preferida, **no se descartan**: caen más abajo en el orden — es el fallback
   automático a la siguiente mejor calidad disponible, no un error.
3. `select_best` devuelve la primera del ranking (`NoAvailableSourceError` si no hay ninguna).
4. `select_by_quality` filtra por calidad exacta (`QualityNotAvailableError` si no existe).

### 18.3 Playback Services (casos de uso)

`application/playback/use_cases/`, uno por servicio pedido:

| Servicio pedido | Caso(s) de uso |
|---|---|
| Resolver fuentes | `GetEpisodePlayback` (arma todo: metadata+fuentes+calidades), `GetPlaybackSources` |
| Seleccionar calidad | `GetAvailableQualities`, `SelectPlaybackQuality` |
| Seleccionar subtítulos | `GetAvailableSubtitles`, `SelectPlaybackSubtitle` |
| Administrar sesiones | `CreatePlaybackSession`, `SelectPlaybackSource` |
| Guardar progreso | `SaveWatchProgress` (marca `COMPLETED` automáticamente vía `ResumePointService` si el progreso llega cerca del final), `GetWatchProgress`, `GetResumePoint` |

Más navegación (no listada como "servicio" pero sí como capacidad de API):
`GetNextEpisode`/`GetPreviousEpisode` — cruzan de temporada automáticamente (último episodio de
una temporada → primer episodio de la siguiente, y viceversa), usando `AnimeRepository` (ya
existía desde el Sprint 2) porque ningún repositorio soporta "a qué Season pertenece este
Episode" directo (`application/playback/catalog_lookup.py` resuelve esto recorriendo
`Anime.seasons` una vez).

`GetPlaybackSources`/`GetAvailableQualities`/`GetAvailableSubtitles` no repiten lógica: delegan
en `GetEpisodePlayback` y proyectan el campo que les toca — un solo lugar resuelve
catálogo+fuentes+cache.

### 18.4 Playback API (primeros endpoints HTTP reales)

`infrastructure/http/routers/playback_router.py` + `infrastructure/http/schemas/playback_schemas.py`.
Cada handler traduce Schema → DTO/Command → caso de uso → DTO → Schema; ningún caso de uso
conoce FastAPI ni Pydantic (mismo principio que en toda la capa `application/`).

| Método | Ruta | Caso de uso |
|---|---|---|
| GET | `/animes/{anime_id}/episodes/{episode_id}/playback` | `GetEpisodePlayback` |
| GET | `/animes/{anime_id}/episodes/{episode_id}/playback/sources` | `GetPlaybackSources` |
| GET | `/animes/{anime_id}/episodes/{episode_id}/playback/subtitles` | `GetAvailableSubtitles` |
| GET | `/animes/{anime_id}/episodes/{episode_id}/playback/qualities` | `GetAvailableQualities` |
| GET | `/animes/{anime_id}/seasons/{n}/episodes/{n}/next` | `GetNextEpisode` |
| GET | `/animes/{anime_id}/seasons/{n}/episodes/{n}/previous` | `GetPreviousEpisode` |
| POST | `/playback/sessions` | `CreatePlaybackSession` |
| POST | `/playback/sessions/{id}/source` \| `/quality` \| `/subtitle` | `SelectPlayback*` |
| POST | `/playback/sessions/{id}/progress` | `SaveWatchProgress` |
| GET | `/playback/sessions/{id}/progress` | `GetWatchProgress` |
| GET | `/playback/sessions/{id}/resume-point` | `GetResumePoint` |

**Manejo de errores centralizado, ahora con contenido real.** `exception_handlers.py` (definido
vacío desde el Sprint 1 salvo un catch-all 500) ahora traduce `NotFoundError` → 404,
`ConflictError` → 409, `ValidationError` → 422, cualquier otra `DomainError` → 400 — todo
`AnimeNotFoundError`/`PlaybackSessionNotFoundError`/etc. cae en uno de estos por herencia, sin
necesitar un handler propio por excepción concreta.

**Wiring honesto (`deps.py`).** `PlaybackSessionRepository` se resuelve con
`InMemoryPlaybackSessionRepository` real (no un doble): las sesiones son anónimas y de vida
corta, un store de un solo proceso es una elección de producción razonable hoy, no un stopgap.
`CatalogUnitOfWork` (desde un fix posterior al Sprint 10, ver Sección 21.9) sigue el mismo
criterio vía `InMemoryCatalogUnitOfWork` — sin adapter SQLAlchemy todavía (pendiente desde el
Sprint 2), pero ya no lanza `NotImplementedError` por defecto. Los endpoints que lo necesitan
están completamente implementados y probados (`tests/integration/playback/`, vía
`app.dependency_overrides`, patrón estándar de FastAPI para testear), pero correr contra datos
que sobrevivan un restart del proceso espera al adapter SQLAlchemy, no antes.

### 18.5 Cache: solo metadata, nunca progreso

Reusa `ProviderCache`/`InMemoryProviderCache` (Sprint 5) — no se inventó una abstracción de
cache nueva. `GetEpisodePlayback` cachea el `EpisodePlaybackDTO` completo (título, fuentes,
calidades — nada específico de un usuario) por `(anime_id, episode_id)`. `WatchProgress`,
`ResumePoint` y cualquier dato de `PlaybackSession` **nunca pasan por esta cache**: siempre se
leen/escriben directo en `PlaybackSessionRepository` — es la regla explícita de este sprint y
está verificada en `tests/unit/application/playback/test_use_cases.py`
(`SaveWatchProgress`/`GetWatchProgress`/`GetResumePoint` no reciben ningún parámetro de cache).

### 18.6 Tests

- `tests/unit/domain/playback/`: `test_value_objects.py`, `test_entities.py`
  (`PlaybackSource`/`EpisodePlayback`/`PlaybackSession`, incluida la máquina de estados de
  sesión), `test_services.py` (`SourceSelectionService` — fallback y prioridad —,
  `ResumePointService` — los 3 umbrales).
- `tests/unit/application/playback/`: `test_mappers.py` (incluye el caso "sin `url` → se
  omite"), `test_source_resolver.py`, `test_session_store.py`, `test_use_cases.py` (los 12
  casos de uso, incluida navegación next/previous cruzando temporadas).
- `tests/integration/playback/test_playback_api.py`: la app FastAPI real (`httpx.AsyncClient` +
  `ASGITransport`, sin servidor real) con `app.dependency_overrides` inyectando un
  `CatalogUnitOfWork` in-memory — sesión completa (crear → seleccionar calidad/subtítulo →
  guardar progreso → leer progreso/resume-point) y traducción de errores a 404 verificadas de
  punta a punta a través de HTTP real.

### 18.7 Qué falta explícitamente (fuera de alcance de Sprint 7)

- Resolución dinámica de fuentes contra un provider en vivo (requiere una capacidad nueva en
  `ProviderPort`, no construida — ver 18.2).
- Autenticación (sesiones anónimas se quedan así hasta entonces), favoritos, historial,
  comentarios — explícitamente excluidos.
- Adapter SQLAlchemy de `CatalogUnitOfWork` (sigue pendiente desde el Sprint 2).
- Endpoints HTTP para Aggregation Engine (búsqueda/detalle agregados) y para el catálogo
  interno en general (CRUD de `Anime`/`Genre`/etc.) — solo Playback tiene rutas hoy.
- Reproductor real (frontend) — fuera de alcance del backend en cualquier sprint.

**No se implementará nada de esto hasta recibir aprobación explícita.**

## 19. Sprint 8 — API pública

Sprint 8 no agrega dominio nuevo: expone, a través de HTTP, todo lo que Catálogo (Sprint 2),
Aggregation Engine (Sprint 6) y Provider Framework (Sprints 3-5) ya construyeron, empaquetado en
DTOs/Schemas consistentes para que el frontend tenga una única superficie estable. Reproducción
(Sprint 7) queda fuera a propósito — no se tocó `playback_router.py` ni su dominio.

### 19.1 Controllers y endpoints

7 routers ("Controllers"), 12 endpoints `GET`, todos bajo prefijo `/api/v1`:

| Controller | Router | Rutas | Caso(s) de uso |
|---|---|---|---|
| AnimeController | `anime_router.py` | `GET /anime`, `GET /anime/{id}`, `GET /anime/{id}/episodes` | `ListCatalog`, `GetAnimeById`, `GetAnimeEpisodes` |
| EpisodeController | `episode_router.py` | `GET /episodes/{id}` | `GetEpisodeById` |
| SearchController | `search_router.py` | `GET /search`, `GET /latest`, `GET /popular` | `SearchAggregatedAnime`, `GetAggregatedLatest`, `GetAggregatedPopular` |
| GenreController | `genre_router.py` | `GET /genres`, `GET /genres/{id}` | `ListGenres`, `GetGenre` |
| CatalogController | `catalog_router.py` | `GET /catalog` | `GetCatalogFacets` |
| ProviderController | `provider_router.py` | `GET /providers` | `ListProviders` |
| HealthController | `health_router.py` (pre-existente, Sprint 1) | `GET /health` | — |

`/anime` soporta filtros por query params (`status`, `type`, `genre_id`, `studio_id`,
`producer_id`, `tag_id`, `q`) y paginación (`page`, `page_size`) reutilizando `ListCatalog`
(Sprint 2) sin cambios. `/search`, `/latest`, `/popular` aceptan `provider_ids` como lista
separada por comas para restringir qué proveedores consulta el `AggregationEngine`.

### 19.2 DTOs, no entidades — casi todo reutilizado

Regla dura del sprint: los routers nunca serializan entidades de dominio ni DTOs directamente,
siempre `Schema.model_validate(dto, from_attributes=True)`. La mayoría de los DTOs ya existían
(`AnimeDetailDTO`/`AnimeSummaryDTO`/`EpisodeDTO`/`GenreDTO` de Sprint 2,
`AggregatedSearchResultDTO` de Sprint 6); solo se agregaron dos:

- `CatalogFacetsDTO` (`application/catalog/dto.py`): tipos/estados estáticos (`AnimeType`,
  `AnimeStatus`) + géneros/estudios/productoras/tags vivos desde los repos — pensado para que el
  frontend arme filtros sin hardcodear enums.
- `ProviderInfoDTO` (`application/providers/dto.py`): combina `ProviderRegistry` +
  `HealthTracker.get_health()` + `StatsTracker.get_stats()` por proveedor — visibilidad
  operativa (salud, prioridad, llamadas totales/exitosas/fallidas, latencia promedio) sin
  exponer el `ProviderPort` interno.

Los Schemas Pydantic (`infrastructure/http/schemas/{catalog,search,provider,common}_schemas.py`)
son un espejo 1:1 de estos DTOs, con `Field(examples=[...])` para que el OpenAPI generado
(`/docs`) tenga ejemplos reales, no solo tipos. `PageSchema[T]` (PEP 695 generic) estandariza
toda respuesta paginada (`items`, `total`, `page`, `page_size`).

### 19.3 Casos de uso nuevos (delgados, sin lógica nueva)

Ningún caso de uso nuevo introduce reglas de negocio: todos reordenan/combinan lo que ya existía.

- `GetAnimeById`, `GetAnimeEpisodes` (aplana episodios de todas las temporadas, ordenados por
  temporada→número), `GetEpisodeById`, `GetGenre`, `GetCatalogFacets` — en `application/catalog/`.
- `GetAggregatedLatest`, `GetAggregatedPopular` — en `application/aggregation/`, wrappers
  delgados sobre `AggregationEngine` (igual patrón que `SearchAggregatedAnime` de Sprint 6).
- `ListProviders` — en `application/providers/`.

**Limitación documentada, no descuido:** `GetEpisodeById` no incluye `season_number` en su
respuesta porque `EpisodeRepository.get_by_id` (Sprint 2) no da contexto de a qué temporada
pertenece el episodio — la misma tensión de diseño ya documentada para `GetEpisodePlaybackQuery`
en el Sprint 7 (18.3).

### 19.4 Errores y wiring

Reutiliza el `exception_handlers.py` del Sprint 7 sin cambios: `NotFoundError` → 404,
`ValidationError` → 422, etc. `deps.py` agrega funciones `get_*_use_case` para cada caso de uso
nuevo, más dos singletons `@lru_cache`:

```python
@lru_cache
def get_provider_manager() -> ProviderManager:
    return ProviderManager()  # empieza vacío: ningún adapter concreto se registra automáticamente

@lru_cache
def get_aggregation_engine() -> AggregationEngine:
    return AggregationEngine(manager=get_provider_manager())
```

Como no hay ningún adapter de proveedor registrado por defecto (Sprint 5 solo construyó el
adapter de Jikan como prueba, no wireado en `deps.py`), `/search`, `/latest`, `/popular` y
`/providers` devuelven listas vacías en un despliegue limpio — comportamiento correcto y
verificado por test (`test_search_with_no_providers_returns_empty_list`,
`test_list_providers_empty_by_default`), no un bug.

### 19.5 Tests

- Unit: un archivo por caso de uso nuevo en `tests/unit/application/{catalog,aggregation,providers}/`,
  usando los mismos fakes de siempre (`FakeCatalogUnitOfWork`, `FakeProviderPort`).
- Integration: `tests/integration/api/test_public_api.py` — mismo patrón que
  `tests/integration/playback/test_playback_api.py` (Sprint 7): `httpx.AsyncClient` +
  `ASGITransport` sobre la app real, `app.dependency_overrides` inyectando
  `FakeCatalogUnitOfWork` + `ProviderManager` con un `FakeProviderPort` registrado. 19 tests:
  las 7 controllers, casos 404, filtro por género, 422 en `/search` sin `q`, y los dos casos de
  "vacío por defecto" (sin proveedores registrados).
- Cobertura: 98% total del proyecto; 100% en todos los routers/schemas nuevos salvo
  `search_router.py` (96%) y `playback_router.py` (97%, sin cambios de Sprint 7).

### 19.6 Qué falta explícitamente (fuera de alcance de Sprint 8)

- Autenticación — todos los endpoints son públicos y de solo lectura (`GET`).
- Reproducción — Sprint 7 queda como está, no se extendió.
- Favoritos, historial — explícitamente excluidos.
- Adapter SQLAlchemy de `CatalogUnitOfWork` (pendiente desde el Sprint 2: `get_catalog_unit_of_work()`
  sigue lanzando `NotImplementedError` fuera de tests).
- Ningún adapter de proveedor registrado por defecto en `deps.py` — `/search`/`/latest`/`/popular`/`/providers`
  funcionan pero devuelven vacío hasta que un sprint futuro wiree el adapter de Jikan (u otros).

**No se implementará nada de esto hasta recibir aprobación explícita.**

## 20. Sprint 9 — Identity Module

Sprint 9 agrega un módulo de identidad (autenticación + autorización)
**completamente nuevo y desacoplado**: ni `domain/catalog`, ni
`domain/providers`, ni `domain/playback` cambiaron una sola línea en este
sprint, y `application/identity`/`infrastructure/identity` no importan
nada de `application/providers` (Provider Framework) — es un eje de
extensibilidad completamente distinto, con su propia arquitectura de
"Authentication Providers" pluggable, su propio registry, su propio rate
limiter y su propia protección de fuerza bruta.

### 20.1 `domain/identity/` — dominio nuevo, dominio existente intacto

```
domain/identity/
├── value_objects.py   # UserId, RoleId, PermissionId, CredentialId, SessionId,
│                        # RefreshTokenId, Email, Username, Profile, UserSettings, Identity
├── entities.py         # Permission, Role, Credential, Session, RefreshToken, User (Aggregate Root)
├── services.py         # PasswordPolicy, AuthorizationService
└── exceptions.py
```

**`Identity` no es `User`.** Distinción deliberada (mismo espíritu que
"DTO ≠ entidad" en capas superiores, pero acá dentro del propio dominio):
`User` es el Aggregate Root persistido (fuente de verdad, se lee/escribe
en `IdentityRepository`); `Identity` (`domain.identity.value_objects.Identity`)
es una foto inmutable de los claims (`roles`/`permissions` ya resueltos a
strings `"resource:action"`) tal como quedaron grabados en el
`AccessToken` al emitirse. Todo `AuthorizationService` opera sobre
`Identity` — nunca vuelve a golpear un repositorio para autorizar un
pedido ya autenticado.

**`AccessToken` es deliberadamente "invisible" como entidad propia.** Se
modela como claims de JWT (`sub`, `email`, `roles`, `permissions`, `iat`,
`exp`, `jti`) que `TokenService` (puerto de aplicación) emite/decodifica
— no hay una clase `AccessToken` persistida porque un JWT es, por
diseño, stateless: su propia firma es la prueba de validez, no necesita
una fila en una tabla para ser consultado. `RefreshToken`, en cambio, SÍ
es una entidad persistida (`domain.identity.entities.RefreshToken`)
porque necesita poder revocarse activamente — la asimetría es
intencional, no una omisión.

**`RefreshToken` nunca persiste el valor crudo**, solo `token_hash`
(mismo principio que un password: si la tabla se filtra, no debe filtrar
tokens usables). Token Rotation vive en la propia entidad:
`RefreshToken.rotate(new_token_id)` marca `rotated_to` y deja el token
inutilizable; si se llama `rotate()` sobre un token que ya tiene
`rotated_to` seteado (o que está revocado/expirado), levanta
`RefreshTokenReusedError` — la señal de que alguien está reutilizando un
token ya usado, evidencia de robo. El caso de uso (`RefreshAccessToken`,
ver 20.3) traduce esa excepción en revocar TODA la sesión, no solo
rechazar el pedido.

**`PasswordPolicy`** (dominio, puro): mínimo 8 caracteres, mayúscula,
minúscula y dígito — valida el password en texto plano ANTES de
hashearlo (hashear es infraestructura, ver 20.4).

**`AuthorizationService`** (dominio, puro): RBAC + policies sobre una
`Identity` ya resuelta.
`AuthorizationService.authorize(identity, resource, action, policies=[...])`
levanta `InactiveUserError`/`PermissionDeniedError` si no está permitido.
`Policy` es `Callable[[Identity], bool]` — un predicado adicional
evaluado DESPUÉS del chequeo RBAC básico (AND, nunca reemplaza al
permiso), pensado para reglas tipo "solo el dueño del recurso" en
sprints futuros que expongan endpoints protegidos por permisos
específicos (ninguno de los 7 endpoints de este sprint lo necesita más
allá de "estar autenticado").

### 20.2 Authentication Provider architecture

El requisito central del sprint: soportar múltiples estrategias de login
sin tocar dominio ni casos de uso al agregar una nueva.

```
application/identity/
├── ports.py      # AuthenticationProvider (Protocol), TokenService, PasswordHasher,
│                  # BruteForceGuard, IdentityUnitOfWork + 6 repos
├── registry.py    # AuthenticationProviderRegistry
├── dto.py / mappers.py / loaders.py
└── use_cases/      # register_user, login_user, logout_user, refresh_access_token,
                     # get_current_user, update_profile, update_settings
```

`AuthenticationProvider` (puerto) declara `provider_id` +
`authenticate(credentials, uow) -> User`. `AuthenticationProviderRegistry`
(aplicación) es una implementación **propia e independiente** de
`application.providers.registry.ProviderRegistry` (Provider Framework) —
misma forma de patrón (registro por id, `.get()`/`.register()`), cero
código compartido, a propósito: son dos ejes de extensibilidad
completamente distintos (de dónde sale el catálogo vs. quién es el
usuario).

Primera y única estrategia implementada hoy:
`infrastructure.identity.providers.password_provider.PasswordAuthenticationProvider`
(`provider_id = "password"`) — busca el `User` por email, su `Credential`
tipo `"password"`, y compara con `PasswordHasher.verify`. Una estrategia
nueva (Google/GitHub OAuth, magic-link, WebAuthn) se agrega escribiendo
otra clase que implemente el mismo `AuthenticationProvider` Protocol y
registrándola en `infrastructure.http.deps.get_authentication_provider_registry`
— cero cambios en `domain/identity`, en `LoginUser`, ni en ningún otro
caso de uso.

### 20.3 Casos de uso

| Endpoint | Caso de uso | Nota |
|---|---|---|
| `POST /auth/register` | `RegisterUser` | Valida `PasswordPolicy`, unicidad de email/username, asigna el rol `"user"` (sembrado por defecto). |
| `POST /auth/login` | `LoginUser` | `BruteForceGuard.is_blocked` → `AuthenticationProviderRegistry.get("password").authenticate` → crea `Session` → emite `AccessToken`+`RefreshToken`. |
| `POST /auth/logout` | `LogoutUser` | Revoca la `Session` completa (y con ella, todo `RefreshToken` vivo bajo esa sesión) — un logout es una revocación completa, no "olvidar" un token. |
| `POST /auth/refresh` | `RefreshAccessToken` | Token Rotation + detección de reuso (ver 20.1). |
| `GET /auth/me` | `GetCurrentUser` | Recibe la `Identity` ya decodificada (`deps.get_current_identity`) y carga el `User` fresco — el token puede tener roles/permisos ligeramente desactualizados si cambiaron después de emitirse. |
| `PATCH /auth/profile` | `UpdateProfile` | Semántica PATCH: campos `None` conservan el valor actual de `Profile`. |
| `PATCH /auth/settings` | `UpdateSettings` | Misma semántica PATCH sobre `UserSettings`. |

`application/identity/loaders.py::load_roles_and_permissions` factoriza
la composición `User.role_ids -> Roles -> permission_ids -> Permissions`
repetida por casi todos los casos de uso, para no duplicarla.

### 20.4 Infraestructura: JWT, Argon2, in-memory real por defecto

```
infrastructure/identity/
├── jwt_token_service.py         # TokenService — PyJWT (HS256)
├── password_hasher.py            # PasswordHasher — Argon2id (argon2-cffi)
├── brute_force_guard.py          # BruteForceGuard — ventana fija en memoria
├── security_middleware.py        # SecurityHeadersMiddleware, AuthRateLimitMiddleware
├── providers/password_provider.py
└── repositories/in_memory_identity_repository.py   # IdentityUnitOfWork real por defecto
```

- **JWT Authentication**: `JwtTokenService` (PyJWT, `HS256` configurable
  vía `Settings.jwt_algorithm`/`jwt_secret_key`). El `AccessToken` lleva
  `roles`/`permissions` ya resueltos como claims — así `get_current_identity`
  (dependencia HTTP) no necesita golpear ningún repositorio para
  autorizar, solo decodificar y verificar la firma.
- **Password Hashing**: `Argon2PasswordHasher` (Argon2id vía
  `argon2-cffi`, recomendado por OWASP sobre bcrypt/PBKDF2 para hashes
  de contraseña nuevos).
- **Refresh Token hashing**: SHA-256 simple (`hashlib`), no Argon2 — a
  diferencia de un password (baja entropía, elegido por un humano), un
  refresh token ya es un secreto de alta entropía por construcción
  (`secrets.token_urlsafe(48)`), no necesita un hash lento.
- **`InMemoryIdentityUnitOfWork`**: implementación real por defecto (no
  un doble de test), mismo criterio que
  `InMemoryPlaybackSessionRepository` del Sprint 7. Se siembra a sí misma
  en el constructor (síncrono, sin I/O real detrás) con los roles base
  `"user"` (`profile:read`, `profile:update`, `catalog:read`) y `"admin"`
  (los 4 permisos base, incluido `admin:manage`) — así `RegisterUser`
  siempre encuentra el rol por defecto sin un paso de seed aparte.
- **Brute Force Protection**: `InMemoryBruteForceGuard`, ventana fija
  (5 fallos / 15 min por defecto) sobre la key `email:ip`; un login
  exitoso limpia el contador. Independiente del `RateLimiter` del
  Provider Framework (Sprint 4) a propósito.
- **Rate Limiting**: `AuthRateLimitMiddleware` (Starlette
  `BaseHTTPMiddleware`), 30 requests/60s por IP, aplicado solo a
  `/api/v1/auth/*` — defensa de transporte contra flood, complementaria
  (no redundante) al `BruteForceGuard`, que limita intentos fallidos por
  credencial, no requests en bruto.
- **Headers de Seguridad**: `SecurityHeadersMiddleware` aplica a TODA la
  app (no solo `/auth`): `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security`.

### 20.5 RBAC: roles y permisos base

| Rol | Permisos |
|---|---|
| `user` (asignado en `register`) | `profile:read`, `profile:update`, `catalog:read` |
| `admin` | los 4 permisos base, incluido `admin:manage` |

Los permisos siguen el formato `"{resource}:{action}"` (`Permission.key`)
— el mismo string viaja en el `AccessToken` y es lo que
`AuthorizationService.has_permission` compara. Ninguno de los 7 endpoints
de este sprint requiere más que "estar autenticado" (son autogestión:
`/me`, `/profile`, `/settings`), pero el mecanismo RBAC completo
(`AuthorizationService.authorize` con `resource`/`action`/`policies`)
queda disponible para que un sprint futuro proteja endpoints
administrativos sin volver a tocar el dominio.

### 20.6 Errores: 3 códigos HTTP nuevos

`domain/identity/exceptions.py` introduce `IdentityError(DomainError)` y,
bajo ella, `AuthenticationError` (401) y `PermissionDeniedError` (403) —
las primeras excepciones de dominio en todo el proyecto que no encajan en
`NotFoundError`/`ConflictError`/`ValidationError` (404/409/422).
`TooManyAttemptsError` (429) cubre bloqueo por fuerza bruta.
`exception_handlers.py` (Sprint 7) se extendió con 3 handlers nuevos —
mismo principio de siempre: ninguna excepción concreta
(`InvalidCredentialsError`, `RefreshTokenReusedError`, ...) necesita su
propio handler, alcanza con las clases base.

| Excepción base | HTTP | Ejemplos concretos |
|---|---|---|
| `AuthenticationError` | 401 | `InvalidCredentialsError`, `RefreshTokenReusedError`, `RefreshTokenExpiredError`, `SessionExpiredError`, token JWT inválido/expirado |
| `PermissionDeniedError` | 403 | Falta un permiso RBAC o una policy lo deniega |
| `TooManyAttemptsError` | 429 | `BruteForceGuard` bloqueó la key `email:ip` |
| `UserAlreadyExistsError` (`ConflictError`) | 409 | Email/username duplicado en `register` |
| `WeakPasswordError` (`ValidationError`) | 422 | No cumple `PasswordPolicy` |

`InvalidCredentialsError` usa deliberadamente el mismo mensaje/tipo tanto
si el email no existe como si la contraseña no coincide: no debe ser
posible enumerar emails registrados observando la respuesta de error.

### 20.7 Tests

- `tests/unit/domain/identity/`: `test_value_objects.py`,
  `test_entities.py` (incluye Token Rotation y detección de reuso a
  nivel de entidad), `test_services.py` (`PasswordPolicy`,
  `AuthorizationService` con policies).
- `tests/unit/application/identity/`: `test_registry.py`,
  `test_mappers.py`, `use_cases/` (uno por caso de uso, 7 archivos,
  reutilizando `InMemoryIdentityUnitOfWork` real + fakes propios de
  `PasswordHasher`/`TokenService`/`BruteForceGuard` en
  `tests/unit/application/identity/fakes.py`).
- `tests/unit/infrastructure/identity/`: `test_password_hasher.py`
  (Argon2 real), `test_jwt_token_service.py` (roundtrip, expiración,
  tamper, secret distinto), `test_brute_force_guard.py`,
  `test_password_provider.py`, `test_in_memory_identity_repository.py`.
- `tests/integration/api/test_auth_api.py`: la app FastAPI real
  (`httpx.AsyncClient` + `ASGITransport`) de punta a punta — registro,
  login (incluido bloqueo por fuerza bruta tras 5 fallos), `/me` con y
  sin token, `PATCH /profile`/`/settings`, refresh con rotación,
  **reuso de refresh token detectado y rechazado con 401**, logout. Cada
  test sobreescribe `get_identity_unit_of_work`/`get_brute_force_guard`
  con una instancia fresca (mismo patrón que `test_public_api.py`) y
  fuerza un rebuild de `app.middleware_stack` para que
  `AuthRateLimitMiddleware` no arrastre estado entre tests.

### 20.8 Qué falta explícitamente (fuera de alcance de Sprint 9)

- Adapter SQLAlchemy de `IdentityUnitOfWork` (mismo gap que
  `CatalogUnitOfWork` desde el Sprint 2): `InMemoryIdentityUnitOfWork` es
  el default real hoy, pero no sobrevive un restart del proceso.
  Endpoints de identidad no autorizan en producción hoy — está pendiente.
- Verificación de email (`User.is_verified` existe en el dominio pero
  ningún caso de uso lo activa todavía — no hay endpoint de verificación).
- Segunda estrategia de `AuthenticationProvider` (OAuth/OIDC/magic-link) —
  el mecanismo está listo, no se implementó ninguna concreta más allá de
  `"password"`.
- Endpoints administrativos de gestión de roles/permisos (crear/editar
  roles, asignar permisos por API) — el dominio y `AuthorizationService`
  lo soportan, no hay controller todavía.
- Vincular `PlaybackSession`/favoritos/historial a un `User` autenticado
  — Playback Engine (Sprint 7) sigue siendo anónimo, sin cambios.
- Endpoints protegidos por permiso específico más allá de "estar
  autenticado" (los 7 de este sprint son todos de autogestión).

**No se implementará nada de esto hasta recibir aprobación explícita.**

## 21. Sprint 10 — Web Scraping Provider (AnimeFLV)

Segundo proveedor real de GeekBaku (después de Jikan/MAL, Sprint 5), y el
primero basado en **scraping HTML** en vez de una API oficial —
`https://animeflv.or.at/`, un sitio WordPress sin API pública. El
contrato `ProviderPort` no distingue entre ambos: para
`ProviderManager`/`AggregationEngine`/la API pública, scraping vs. API
oficial es un detalle de implementación invisible — exactamente el punto
de tener la abstracción.

### 21.1 Estructura (mismas 3 piezas que `docs/adding-a-provider.md`)

```
infrastructure/providers/animeflv/
├── client.py     # I/O crudo: URLs, HTTP, HTML tal cual lo devuelve el sitio
├── mapper.py     # Anti-corruption layer: HTML crudo (BeautifulSoup4+lxml) -> DTOs
└── adapter.py    # Implementa ProviderPort combinando client + mapper
```

`client.py` no conoce parsing ni DTOs (solo construye URLs y devuelve
`str` con el HTML), igual que `JikanClient` no conoce nada de JSON
semántico — la única diferencia es que la "forma cruda" acá es HTML en
vez de JSON. `mapper.py` es la única pieza que sabe leer ese HTML
(BeautifulSoup4 + lxml, dependencias nuevas de este sprint).

### 21.2 El sitio no tiene API: una sola ruta, varios query params

`GET /` (WordPress) sirve tres roles según los query params:

| Capacidad | Ruta/params | Notas |
|---|---|---|
| Búsqueda | `/?s={query}` | Grilla dedicada `.search-series-grid .search-series-card`, distinta de la del catálogo. Sin paginación server-side: se pagina del lado del cliente. |
| Catálogo completo | `/?anime_page={n}` | Grilla `.ht_grid_1_4` (WordPress posts, uno por anime). |
| Últimos episodios | `/?episodes_page={n}` | Enlaces a episodios (no a animes); se deriva el anime dueño de cada uno a partir del slug de la URL del episodio. |
| Detalle de anime | `/anime/{slug}/` | Título, sinopsis, géneros, rating, y la lista de episodios embebida como JSON. |
| Página de episodio | URL por fecha, ej. `/2026/07/20/{slug}-episodio-{n}/` | Tabla de servidores de descarga (Mega, MP4Upload, 1Fichier, ...). No derivable desde slug+número: solo se conoce ya resuelta, desde el JSON de la página de detalle. |

**Los episodios no están en el HTML como enlaces.** Se renderizan
client-side (JavaScript) desde un blob JSON embebido:
`<script type="application/json" class="animeflv-episodes-data">[{"post_id":.., "permalink":.., "number":..}, ...]</script>`.
`mapper.parse_episode_refs` lee ese script directamente — no hace falta
ejecutar JavaScript ni un navegador headless, el dato ya está en el HTML
inicial, solo que no como markup `<a>`.

### 21.3 `get_episodes`: N+1 requests, deliberado y acotado

A diferencia de Jikan (`/anime/{id}/episodes` devuelve título+fecha en
una sola llamada, sin fuentes de descarga), AnimeFLV no tiene un
endpoint que devuelva servidores de todos los episodios de una vez: cada
episodio es su propia página. `get_episodes` completo hace 1 request
(detalle del anime, para la lista de referencias) + N requests (una por
episodio, para su tabla de servidores), acotado por un
`asyncio.Semaphore` (`_MAX_CONCURRENT_EPISODE_FETCHES = 5`) para no
floodear el sitio. El costo se paga una vez por TTL de cache
(`ProviderManager` cachea el resultado completo de `get_episodes`), no en
cada request a la API pública de GeekBaku.

### 21.4 Capacidades sin equivalente real en el sitio — documentadas, no adivinadas

Siguiendo la regla de `docs/adding-a-provider.md` ("no lances
`NotImplementedError`, documentá la aproximación"):

- **`get_related`**: el sitio no expone relaciones entre animes (cada
  temporada/entrega es un slug de catálogo independiente, sin cross-links
  navegables). Devuelve siempre `[]`.
- **`get_seasons`**: el sitio no modela "temporadas" dentro de un mismo
  anime (`grand-blue-season-3` es su propio slug de catálogo, no una
  sub-página de un anime "grand-blue" padre). Se devuelve una única
  `ProviderSeasonDTO` (temporada 1, con el conteo de episodios) — mismo
  criterio pragmático que `jikan.mapper.map_season`.
- **`get_popular`**: el sitio no expone ranking real de popularidad (ni
  vistas ni votos ordenables). Se usa la sección "Animes en Emisión" del
  home como proxy honesto — lo más cercano a "qué se está mirando ahora"
  que el sitio publica, documentado explícitamente como una aproximación,
  no una suposición silenciosa.
- **`get_genres`**: el sitio no expone una taxonomía de géneros separada
  (no hay `/genero/{slug}/`). Se hace best-effort: agrega los géneros
  vistos en la primera página del catálogo (clases `genre-{slug}` en cada
  card).
- **`get_types`**: el sitio no separa TV/Movie/OVA/etc. de forma
  navegable. Se usa un vocabulario cerrado estándar como fallback, mismo
  criterio que `jikan.mapper.STATIC_ANIME_TYPES`.

### 21.5 Riesgos propios del scraping (vs. una API)

- **El markup puede cambiar sin aviso.** A diferencia de Jikan (contrato
  JSON documentado y versionado), cualquier rediseño del sitio puede
  romper selectores CSS o el nombre de la clase del script JSON de
  episodios. Cada selector no trivial está comentado en `mapper.py` con
  la estructura concreta que asume, para que un fallo futuro sea fácil de
  diagnosticar.
- **Encoding.** El sitio no siempre declara `charset` en el header
  `Content-Type`; `httpx` puede caer a una detección incorrecta (mojibang
  en acentos/ñ). `AnimeFlvClient` fuerza `response.encoding = "utf-8"`
  explícitamente en vez de confiar en la autodetección.
- **Contaminación de selectores demasiado amplios.** Un primer intento de
  `parse_listing_items` usaba `a[href*="/anime/"]` sobre toda la página,
  lo que también capturaba enlaces de sidebar en la página de búsqueda.
  Se corrigió scopeando cada parser a la grilla/contenedor específico
  (`.ht_grid_1_4` para catálogo/home, `.search-series-card` para
  búsqueda) — un recordatorio de que un selector "que matchea" no es lo
  mismo que un selector "correcto" en HTML de terceros no controlado.
- **Rate limit deliberadamente conservador.** A diferencia de Jikan (API
  pensada para consumo programático), animeflv.or.at es un sitio para
  navegación humana. El `ProviderConfiguration` con el que se registra por
  defecto usa `RateLimitConfig(max_requests=10, period_seconds=60)` — ser
  buen ciudadano de la web aunque el `robots.txt` del sitio no lo exija
  explícitamente (no tiene `Disallow` alguno).

### 21.6 Wireado por defecto (a diferencia de Jikan)

`infrastructure/http/deps.py::get_provider_manager()` ahora registra el
adapter de AnimeFLV automáticamente al construir el `ProviderManager` del
proceso — a diferencia de Jikan (construido en Sprint 5 pero nunca
wireado por defecto, ver Sección 16). Esto significa que, a partir de
este sprint, `/api/v1/search`, `/api/v1/latest`, `/api/v1/popular` y
`/api/v1/providers` devuelven resultados reales out-of-the-box, sin pasos
de configuración adicionales — la integración pedida explícitamente para
este sprint. Jikan sigue sin registrarse por defecto (ver
`docs/adding-a-provider.md` para agregarlo manualmente).

### 21.7 Tests

- `tests/unit/infrastructure/providers/animeflv/test_mapper.py`: parsing
  puro (sin HTTP) con fixtures HTML **sintéticas** que reproducen la
  estructura observada del sitio (clases CSS, JSON embebido) con datos
  ficticios — no contenido real scrapeado guardado en el repo.
- `tests/integration/providers/animeflv/test_adapter.py`: los 9 métodos
  de `ProviderPort` con `respx` interceptando HTTP a nivel de transporte
  (sin red real), incluido 404 → `None` en `get_anime_detail` y el flujo
  completo de `get_episodes` (detalle + N páginas de episodio).
- `tests/integration/providers/animeflv/test_manager_integration.py`:
  `ProviderFactory` → `ProviderManager` real (cache/retry/health, no
  dobles) con el adapter de AnimeFLV — mismo patrón que
  `tests/integration/providers/jikan/test_manager_integration.py`,
  confirma que el Provider Framework funciona igual de bien con un
  adapter de scraping que con una API oficial.
- `tests/integration/api/test_public_api.py`: los dos tests que asumían
  "sin providers por defecto" (`TestSearchController`/
  `TestProviderController`) se actualizaron para sobreescribir
  explícitamente el `ProviderManager` con uno vacío cuando ese es
  específicamente el caso bajo prueba — el default global ya no está
  vacío desde este sprint.

### 21.8 Qué falta explícitamente (fuera de alcance de Sprint 10)

- Un tercer proveedor, o cualquier lógica de deduplicación específica
  entre Jikan y AnimeFLV más allá de lo que ya hace el Aggregation Engine
  (Sprint 6) de forma genérica (matching por título/external id).
- Resolución de los enlaces de descarga (Mega/MP4Upload/1Fichier) a un
  stream reproducible directo — `ProviderSourceDTO.url` guarda la URL del
  host externo tal cual la expone el sitio; seguir esa URL para obtener
  un link de reproducción directo (ej. resolver la API de Mega) es un
  proveedor de un tipo completamente distinto, no scrapeado, fuera de
  alcance acá.
- Wireo automático de AnimeFLV como fuente del Playback Engine
  (`catalog.Episode.streaming_sources`, Sprint 2/7) — hoy vive solo del
  lado del Provider Framework/Aggregation Engine; conectar un resultado
  de `get_episodes` a un `Episode` persistido requiere el adapter
  SQLAlchemy de `CatalogUnitOfWork` (pendiente desde el Sprint 2) más un
  paso de ingesta que no existe todavía.
- Manejo de CAPTCHA/Cloudflare/bloqueo anti-bot — el sitio no los tiene
  hoy (confirmado por `robots.txt` sin restricciones y peticiones
  exitosas con un User-Agent de navegador estándar), pero si los agregara
  en el futuro, este adapter dejaría de funcionar sin aviso — un riesgo
  inherente al scraping, no cubierto por ningún mecanismo de este sprint.

**No se implementará nada de esto hasta recibir aprobación explícita.**

### 21.9 Hotfix posterior: `CatalogUnitOfWork` in-memory por defecto

Al correr `uvicorn --reload` localmente después de este sprint, cualquier
endpoint que dependiera de `CatalogUnitOfWork` (`/anime`, `/genres`,
`/catalog`, ...) crasheaba: `get_catalog_unit_of_work()` lanzaba
`NotImplementedError` por diseño (no existía adapter, ver Sección 19.6),
y nada lo sobreescribía fuera de los tests de integración (que sí usan
`app.dependency_overrides`). Se resolvió con el mismo criterio ya usado
para `PlaybackSessionRepository` (Sprint 7) e `IdentityUnitOfWork`
(Sprint 9): `infrastructure/catalog/repositories/in_memory_catalog_repository.py::InMemoryCatalogUnitOfWork`,
una implementación real por defecto (no un doble de test), wireada como
singleton `@lru_cache` en `deps.get_catalog_unit_of_work()`.

Distinto de `tests/unit/application/catalog/fakes.py::FakeCatalogUnitOfWork`
(que mantiene `episodes` desacoplado de `animes` a propósito, para que
cada test registre solo lo que necesita): acá `InMemoryEpisodeRepository`
recibe el mismo `InMemoryAnimeRepository` en el constructor y busca el
episodio recorriendo `Anime.seasons` de todo lo ya agregado — un default
de desarrollo debe poder resolver cualquier episodio de cualquier anime
agregado, no solo los registrados a mano.

Sigue sin haber persistencia entre restarts del proceso (pendiente el
adapter SQLAlchemy, Sprint 2) — pero el dev server ya no crashea al
levantarse ni al pegarle a `/anime`, `/genres`, `/catalog`, etc. sin
Postgres.

Un mismo gotcha de Python vale la pena dejar anotado: `InMemoryAnimeRepository`
implementa `AnimeRepository.list(...)` (el nombre lo define el Protocol),
y un método de instancia llamado `list` sombrea el `list` builtin para el
resto del cuerpo de la clase — cualquier anotación de tipo `list[...]` en
un método definido DESPUÉS de `list` falla en mypy (`"... .list" is not
valid as a type`). El helper `all_animes(self) -> list[Anime]` se declaró
antes del método `list` específicamente por esto.

## 22. Hotfix posterior: ingesta bajo demanda (provider → catálogo interno)

**El problema real detrás del hotfix de la Sección 21.9**: aun con
`InMemoryCatalogUnitOfWork` funcionando, un resultado de `/api/v1/search`
(que viene de AnimeFLV) no tenía forma de convertirse en algo que
`/api/v1/anime/{id}`, `/api/v1/anime/{id}/episodes` o el Playback Engine
pudieran servir — todos leen del catálogo interno, que nunca se poblaba.
Buscar funcionaba; hacer clic en un resultado no traía nada (ni sinopsis,
ni episodios, ni fuentes para el reproductor).

### 22.1 `IngestAnimeFromProvider`

Nuevo módulo `application/ingestion/` (deliberadamente separado de
`catalog` y de `providers`: es el único punto del sistema que depende de
ambos a la vez, así ninguno de los dos módulos originales se ensucia con
esa dependencia cruzada). Un solo caso de uso:

```
application/ingestion/
├── dto.py           # IngestAnimeCommand(provider_id, external_id)
└── use_cases/
    └── ingest_anime_from_provider.py   # IngestAnimeFromProvider
```

Flujo (`IngestAnimeFromProvider.execute`):

1. Calcula un slug estable a partir de `provider_id` + `external_id`
   (ej. `animeflv-grand-blue-season-3`) y busca si ya existe un `Anime`
   con ese slug — si existe, lo devuelve tal cual (sin volver a pegarle
   al provider): la ingesta es **idempotente**.
2. Si no existe, pide `ProviderManager.get_anime_detail`/`get_episodes`
   pasando un `ExternalReference` con el `provider_id` exacto —
   despacha a UN provider concreto, no hace fan-out agregado (ya se sabe
   de cuál vino el resultado que el usuario clickeó).
3. Usa `application/providers/normalizers.py::to_normalized_anime`
   (existía desde el Sprint 6, documentado ahí mismo como pensado para
   "una futura capa de ingesta") para pasar del vocabulario libre del
   provider a `AnimeType`/`AnimeStatus`.
4. Por cada género crudo, busca-o-crea un `Genre` interno por slug
   (`_get_or_create_genre`) — no asume que ya exista.
5. Arma una única `Season` (número 1: mismo criterio que en todo el
   Provider Framework para providers que no modelan temporadas) con un
   `Episode` por cada `ProviderEpisodeDTO`, y dentro de cada uno, una
   `StreamingSource` por cada `ProviderSourceDTO` — **acá es donde los
   links de Mega/MP4Upload/1Fichier que scrapea el adapter de AnimeFLV
   (Sección 21) se convierten en `Episode.streaming_sources`**, que es
   exactamente lo que el Playback Engine (Sprint 7) ya sabía leer.
6. Persiste todo en una sola transacción y devuelve `AnimeDetailDTO`
   (mismo DTO que cualquier otro endpoint de detalle) — el resto de la
   API pública no necesita saber que este `Anime` vino de un scraper.

**Normalización de calidad/idioma, honesta sobre sus límites**: AnimeFLV
no expone una resolución real por fuente (solo el formato "MP4") ni un
código de idioma estándar (solo texto "SUB"/"LAT" en una tabla) — se
infieren con palabras clave y defaults documentados
(`_normalize_quality` cae a `HD` si no reconoce nada; audio cae a
japonés salvo que la fuente esté marcada como doblaje latino).

### 22.2 Endpoint puente

`GET /api/v1/anime/external/{provider_id}/{external_id}` (`anime_router.py`):
recibe exactamente los campos que ya vienen en cada `source` de un
resultado de `/search`/`/latest`/`/popular`
(`AggregatedSearchResultDTO.sources[].provider_id`/`external_id`), ingiere
si hace falta, y devuelve el mismo `AnimeDetailSchema` que
`GET /anime/{id}` — con `seasons[].episodes[].streaming_sources` ya
poblado. El frontend usa el `id` interno de la respuesta para los
siguientes pasos (`/anime/{id}/episodes`, Playback Engine), exactamente
igual que si el anime hubiese sido creado a mano.

### 22.3 Qué sigue sin resolver

- Sin re-sincronización: si AnimeFLV publica un episodio nuevo después de
  la primera ingesta, no hay ningún mecanismo que lo detecte — el `Anime`
  interno queda congelado en el estado del momento en que se ingirió. Un
  sprint futuro podría reingresar/mergear si la fecha de ingesta es vieja.
- Un mismo anime en dos providers distintos (ej. Jikan + AnimeFLV) genera
  dos `Anime` internos separados (slugs distintos) — no hay deduplicación
  a nivel de catálogo interno, solo a nivel de `AggregationEngine`
  (Sprint 6), que opera sobre resultados efímeros, no sobre lo persistido.
- Sin autenticación/permisos sobre quién puede disparar una ingesta — hoy
  cualquier request a `GET /anime/external/...` la dispara.

**No se implementará nada de esto hasta recibir aprobación explícita.**

## 23. Hotfix posterior: reemplazo de AnimeFLV por TioAnime

`animeflv.or.at` dejó de responder. Se construyó un tercer adapter,
`infrastructure/providers/tioanime/` (scraping de `https://tioanime.com/`),
con la misma estructura de 3 piezas (`client.py`/`mapper.py`/`adapter.py`)
que Jikan y AnimeFLV, y se lo registró en `deps.get_provider_manager()`
**en lugar de** AnimeFLV — el código de AnimeFLV sigue existiendo tal
cual (con sus tests), simplemente ya no se wirea por defecto, mismo
tratamiento que Jikan.

### 23.1 Por qué TioAnime es más simple de scrapear que AnimeFLV

- **Búsqueda real vía JSON**: `GET /api/search?value={query}` devuelve
  `[{"id","title","slug","type"}]` en JSON limpio — no hace falta parsear
  HTML de una grilla como en AnimeFLV.
- **Episodios sin request extra**: la página de detalle embebe
  `var episodes = [3,2,1];` (los números, no una URL por episodio) y la
  URL de cada uno se arma directo como `/ver/{slug}-{numero}` — no hace
  falta un JSON con `permalink` como en AnimeFLV (donde la fecha en la
  URL no era derivable). `get_episodes` sigue haciendo 1+N requests (el
  detalle + una página por episodio, para los links de reproducción),
  pero sin el paso intermedio de resolver permalinks.
- **Fuentes de embed, no de descarga**: `var videos = [["Mega", embed_url, ...]]`
  son URLs de iframe listas para insertar en un `<video>`/`<iframe>`, no
  links de descarga como Mega/MP4Upload/1Fichier de AnimeFLV.
- **Datos embebidos como asignación JS directa**, no un
  `<script type="application/json">` propio como en AnimeFLV — `mapper.py`
  los extrae con una regex (`_extract_js_array`, con `re.DOTALL` porque el
  array puede venir en varias líneas) y los parsea como JSON (la sintaxis
  de un array JS simple con strings/números es JSON válido).

### 23.2 "Nada de hentai" — garantía en dos capas, no una

Requisito explícito del usuario. TioAnime resuelve esto de forma
estructural, no solo por filtro:

1. **El sitio de contenido para adultos es un dominio completamente
   distinto** (`tiohentai.com`, un sitio hermano/afiliado enlazado desde
   el menú de tioanime.com). `client.py` (`TioAnimeClient`) solo
   construye URLs bajo `DEFAULT_BASE_URL = "https://tioanime.com"` — no
   hay ningún método, configuración, ni referencia en el código que
   apunte a `tiohentai.com`. La garantía no depende de "filtrar bien":
   depende de que el adapter no sabe que ese dominio existe.
2. **Filtro defensivo por género** (`mapper.is_adult_genre`, palabras
   clave `hentai`/`adulto`/`adult`/`xxx`), aplicado en dos puntos:
   - `get_genres()` excluye cualquier género que matchee de la lista de
     géneros pública (hoy el directorio de tioanime.com no tiene
     ninguno — confirmado explorando los 39 géneros reales del filtro).
   - `get_anime_detail()` rechaza (devuelve `None`, como "no existe") si
     el detalle scrapeado trae algún género adulto — defensa en
     profundidad por si el sitio cambiara en el futuro, no algo que se
     espere disparar hoy.

   Nota de diseño: `mapper.parse_anime_detail` deja los géneros SIN
   filtrar en el DTO que devuelve (a diferencia de `parse_genre_names`,
   que sí filtra) — si filtrara ahí, el adapter nunca podría ver que
   había un género adulto para poder rechazar el anime completo. El
   filtro de la taxonomía pública (`get_genres`) y el guard de rechazo
   (`get_anime_detail`) son responsabilidades distintas.

### 23.3 Tests

Mismo esquema que AnimeFLV: `tests/unit/infrastructure/providers/tioanime/test_mapper.py`
(fixtures HTML/JSON sintéticas, incluye un test explícito de que
`is_adult_genre`/`parse_genre_names` excluyen contenido adulto),
`tests/integration/providers/tioanime/test_adapter.py` (respx, incluye un
test de que `get_anime_detail` devuelve `None` ante un género adulto
simulado), `tests/integration/providers/tioanime/test_manager_integration.py`
(`ProviderFactory`→`ProviderManager` real).

**No se implementará nada de esto hasta recibir aprobación explícita.**
