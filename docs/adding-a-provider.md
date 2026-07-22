# Cómo agregar un nuevo proveedor a GeekBaku

Esta guía documenta el procedimiento completo para integrar un nuevo proveedor de contenido de
streaming al Provider Framework. Sigue exactamente los pasos usados para construir el adapter
de referencia (`infrastructure/providers/jikan/`, contra la API pública de Jikan/MyAnimeList).

> Regla de oro: **el dominio (`domain/`) nunca cambia para agregar un proveedor**. Todo lo que
> hace falta vive en `infrastructure/providers/<tu-proveedor>/` (el adapter) y, para registrarlo
> en runtime, en el composition root. Si sentís que necesitás tocar `domain/catalog` o
> `domain/providers` para que tu proveedor "encaje", es una señal de que te falta usar mejor la
> normalización (`application/providers/normalizers.py`), no de que el dominio deba ceder ante
> las particularidades de un proveedor.

## 1. Panorama: qué vas a construir

```
infrastructure/providers/<tu_proveedor>/
├── __init__.py
├── client.py     # I/O crudo: URLs, HTTP, JSON tal cual lo devuelve el proveedor
├── mapper.py     # Anti-corruption layer: JSON crudo -> DTOs de application/providers/dto.py
└── adapter.py    # Implementa ProviderPort combinando client + mapper
```

Tres piezas, cada una con una única responsabilidad:

| Archivo | Responsabilidad | Qué NO hace |
|---|---|---|
| `client.py` | Construir requests HTTP y devolver JSON crudo | No conoce DTOs ni dominio; no reintenta ni cachea |
| `mapper.py` | Traducir JSON crudo → DTOs (`ProviderAnimeDTO`, `SearchResultDTO`, ...) | Nunca devuelve el JSON crudo hacia afuera del paquete |
| `adapter.py` | Implementar `ProviderPort` combinando `client` + `mapper` | No implementa retry/timeout/cache/circuit breaker — eso lo hace `ProviderManager` para *cualquier* provider, de forma genérica |

## 2. Implementar `ProviderPort`

`ProviderPort` (`application/providers/ports.py`) es la interfaz que **todo** proveedor debe
implementar exactamente, sin excepciones ni métodos opcionales:

```python
class ProviderPort(Protocol):
    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]: ...
    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None: ...
    async def get_episodes(self, reference: ExternalReference) -> list[ProviderEpisodeDTO]: ...
    async def get_seasons(self, reference: ExternalReference) -> list[ProviderSeasonDTO]: ...
    async def get_related(self, reference: ExternalReference) -> list[ProviderRelatedDTO]: ...
    async def get_latest(self, pagination: Pagination) -> list[SearchResultDTO]: ...
    async def get_popular(self, pagination: Pagination) -> list[SearchResultDTO]: ...
    async def get_genres(self) -> list[str]: ...
    async def get_types(self) -> list[str]: ...
```

No hace falta heredar de `ProviderPort` explícitamente (es un `Protocol`, PEP 544): con que tu
clase implemente estos 9 métodos con esa firma alcanza — el chequeo es estructural (`mypy` lo
valida en tiempo de desarrollo).

Si tu proveedor real no soporta alguna capacidad de forma nativa (ej. Jikan no tiene un
endpoint de "temporadas" por anime), **igual tenés que implementar el método**: devolvé el
resultado más razonable que puedas derivar de otra información disponible, y documentá la
decisión con un comentario. No lances `NotImplementedError` — eso rompe silenciosamente
cualquier caso de uso que llame a esa capacidad. Ver `mapper.map_season` en el adapter de Jikan
como ejemplo de una aproximación pragmática y documentada.

## 3. `client.py`: I/O crudo

```python
class MiProveedorClient:
    def __init__(self, http_client: httpx.AsyncClient, base_url: str) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")

    async def search_anime(self, query: str, page: int, limit: int) -> dict:
        response = await self._http.get(
            f"{self._base_url}/search", params={"q": query, "page": page, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

    # ... un método por endpoint que necesites
```

Puntos clave:
- El `httpx.AsyncClient` se **inyecta** en el constructor, nunca se crea dentro de `client.py`.
  Esto es lo que permite interceptarlo con `respx` en tests de integración sin red real.
- `response.raise_for_status()` deja que `httpx.HTTPStatusError`/`httpx.RequestError` se
  propaguen tal cual — no los captures ni los envuelvas acá. `ProviderManager` ya sabe
  reintentar/aplicar circuit breaker ante cualquier `Exception`; hacerlo también en `client.py`
  sería resiliencia duplicada.
- Si tu proveedor devuelve `404` para "no existe" (en vez de un cuerpo vacío), manejalo en
  `adapter.py` (no en `client.py`): ver el ejemplo de `get_anime_detail` más abajo.

## 4. `mapper.py`: la capa anti-corrupción

Una función pura por forma de dato, todas con la misma forma: `dict crudo -> DTO`.

```python
PROVIDER_ID = "mi_proveedor"  # el ProviderId con el que se registra en el Manager

def map_search_result(raw: dict) -> SearchResultDTO:
    return SearchResultDTO(
        provider_id=PROVIDER_ID,
        external_id=str(raw["id"]),
        title=raw["title"],
        thumbnail_url=raw.get("cover_url"),
        anime_type=raw.get("format"),
        year=raw.get("year"),
    )
```

Reglas:
- **Nunca** devuelvas ni aceptes como parámetro público un tipo del JSON crudo desde
  `adapter.py` hacia afuera — ni siquiera como `dict` "de paso". Todo lo que sale de
  `mapper.py` es ya un DTO de `application/providers/dto.py`.
- Accedé a los campos crudos siempre con `.get(...)` y valores por defecto — un proveedor
  externo puede omitir campos opcionales sin avisar; que falte un campo no debería tumbar el
  mapeo completo.
- Si tu proveedor usa un vocabulario libre para tipo/estado/relación (ej. `"Currently Airing"`,
  `"Sequel"`), **no** inventes tu propia normalización: reusá
  `application/providers/normalizers.py` (`normalize_type`, `normalize_status`,
  `normalize_relation_type`) pasando el string crudo — esas funciones ya están pensadas para
  vocabulario heterogéneo entre proveedores. Tu `mapper.py` solo arma el `ProviderAnimeDTO`/
  `ProviderRelatedDTO` con el campo `raw_type`/`raw_status`/`raw_relation_type` sin normalizar
  todavía: la normalización ocurre después, en `application/providers/normalizers.py`, cuando
  un caso de uso llama a `to_normalized_anime`/`to_normalized_related`.

## 5. `adapter.py`: atar todo junto

```python
class MiProveedorAdapter:
    def __init__(self, client: MiProveedorClient) -> None:
        self._client = client

    async def search(self, query: str, pagination: Pagination) -> list[SearchResultDTO]:
        raw = await self._client.search_anime(query, pagination.page, pagination.page_size)
        return [mapper.map_search_result(item) for item in raw["results"]]

    async def get_anime_detail(self, reference: ExternalReference) -> ProviderAnimeDTO | None:
        try:
            raw = await self._client.get_detail(reference.external_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return mapper.map_anime_detail(raw)

    # ... el resto de los métodos de ProviderPort
```

Y un constructor de fábrica para registrar en `ProviderFactory`:

```python
def create_mi_proveedor_adapter(configuration: ProviderConfiguration) -> MiProveedorAdapter:
    http_client = httpx.AsyncClient(timeout=configuration.timeout_seconds)
    client = MiProveedorClient(http_client, base_url=configuration.base_url)
    return MiProveedorAdapter(client)
```

## 6. Registrar el proveedor

En el composition root (o, para pruebas exploratorias, donde estés armando el `ProviderManager`):

```python
from geekbaku.application.providers.factory import ProviderFactory
from geekbaku.application.providers.manager import ProviderManager
from geekbaku.domain.providers.value_objects import (
    CacheConfig, ProviderConfiguration, ProviderId, RateLimitConfig, RetryConfig,
)

factory = ProviderFactory()
factory.register_constructor("mi_proveedor", create_mi_proveedor_adapter)

configuration = ProviderConfiguration(
    provider_id=ProviderId("mi-proveedor"),
    base_url="https://api.mi-proveedor.com",
    timeout_seconds=8.0,
    rate_limit=RateLimitConfig(max_requests=60, period_seconds=60),   # opcional
    retry=RetryConfig(max_attempts=3, backoff_base_seconds=0.5),       # opcional, éste es el default
    cache=CacheConfig(enabled=True, ttl_seconds=300),                  # opcional, éste es el default
)

adapter = factory.create("mi_proveedor", configuration)

manager = ProviderManager(cache=InMemoryProviderCache())  # o el ProviderManager compartido de la app
manager.register(
    configuration.provider_id,
    adapter,
    priority=10,       # mayor prioridad = se consulta antes en fan-out (search/latest/popular)
    is_enabled=True,
    configuration=configuration,
)
```

A partir de acá, el proveedor:
- Participa automáticamente en `search`/`get_latest`/`get_popular` (fan-out agregado, ordenado
  por prioridad) sin tocar ningún caso de uso.
- Tiene su propio rate limit, retry, timeout y circuit breaker (según su `ProviderConfiguration`),
  gestionados enteramente por `ProviderManager` — el adapter no implementa nada de eso.
- Puede deshabilitarse en caliente con `manager.disable(configuration.provider_id)` (se excluye
  del fan-out; sigue siendo alcanzable si se lo pide explícitamente vía `provider_ids=(...)`) y
  rehabilitarse con `manager.enable(...)`.
- Expone estadísticas vía `manager.get_stats(configuration.provider_id)` y salud vía
  `manager.get_health(configuration.provider_id)`.

## 7. Testear el nuevo adapter

Dos niveles, igual que en `jikan/`:

**Unit tests de `mapper.py`** (`tests/unit/infrastructure/providers/<tu_proveedor>/test_mapper.py`):
sin HTTP, con fixtures de diccionarios representando el JSON crudo, verificando que cada
función de mapeo produce el DTO esperado (incluyendo casos con campos opcionales faltantes).

**Integration tests de `adapter.py`** (`tests/integration/providers/<tu_proveedor>/test_adapter.py`):
con [`respx`](https://lundberg.github.io/respx/) interceptando `httpx` a nivel de transporte —
nunca hay red real, pero se ejercita el camino completo (URL, params, parsing, mapeo):

```python
import httpx
import respx

@respx.mock
async def test_search_returns_normalized_results() -> None:
    respx.get("https://api.mi-proveedor.com/search").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1, "title": "Frieren"}]})
    )
    adapter = MiProveedorAdapter(MiProveedorClient(httpx.AsyncClient(), base_url="https://api.mi-proveedor.com"))

    results = await adapter.search("frieren", Pagination())

    assert results[0].title == "Frieren"
```

No es necesario un mock del `ProviderPort` completo para testear el adapter: `respx` mockea un
nivel más abajo (transporte HTTP), que es justamente lo que hace a estos tests "de
integración" — prueban que tu adapter arma bien la request y parsea bien la response, no solo
que "algo" implementa la interfaz.

Opcionalmente, un test de integración adicional que registre el adapter en un `ProviderManager`
real (no un doble) demuestra que retry/cache/circuit breaker funcionan también con tu adapter
concreto — ver `tests/integration/providers/jikan/test_manager_integration.py` como referencia.

## 8. Checklist final

- [ ] `client.py`: un método por endpoint, `httpx.AsyncClient` inyectado, sin retry/cache propios.
- [ ] `mapper.py`: una función pura por forma de dato, siempre devuelve DTOs (nunca JSON crudo),
      usa `normalizers.py` para vocabulario libre (tipo/estado/relación).
- [ ] `adapter.py`: implementa los 9 métodos de `ProviderPort`, maneja `404` → `None` en
      `get_anime_detail` si tu proveedor lo usa así, expone `create_<proveedor>_adapter(config)`.
- [ ] Se registra vía `ProviderFactory.register_constructor` + `ProviderManager.register`.
- [ ] Tests unitarios de `mapper.py` con fixtures representativas (incluyendo campos faltantes).
- [ ] Tests de integración de `adapter.py` con `respx` (sin red real).
- [ ] `mypy --strict` y `ruff check` limpios.
- [ ] **No se tocó nada bajo `domain/`.**
