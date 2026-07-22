"""Test de integración del Identity API: ejercita la app FastAPI real de
punta a punta (`httpx.AsyncClient` + `ASGITransport`, sin servidor real).

`get_identity_unit_of_work` es un singleton `@lru_cache` a nivel de
proceso (correcto en producción: todos los requests deben ver el mismo
store in-memory); acá se sobreescribe con una instancia fresca por test
vía `app.dependency_overrides`, igual que `test_public_api.py` hace con
`get_catalog_unit_of_work` — para que un test no vea usuarios creados por
otro.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.app import app
from geekbaku.infrastructure.identity.brute_force_guard import InMemoryBruteForceGuard
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)

REGISTER_PAYLOAD = {
    "email": "ash@geekbaku.dev",
    "username": "ash_ketchum",
    "password": "Pikachu123",
}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    uow = InMemoryIdentityUnitOfWork()
    guard = InMemoryBruteForceGuard()
    app.dependency_overrides[deps.get_identity_unit_of_work] = lambda: uow
    app.dependency_overrides[deps.get_brute_force_guard] = lambda: guard
    # `AuthRateLimitMiddleware` lleva estado propio (`_hits`) cacheado en
    # `app.middleware_stack` durante toda la vida del proceso — forzar un
    # rebuild acá le da a cada test una ventana de rate limit fresca, igual
    # que `uow`/`guard` de arriba.
    app.middleware_stack = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


async def _register_and_login(client: AsyncClient) -> dict[str, object]:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    body: dict[str, object] = response.json()
    return body


class TestRegister:
    async def test_register_returns_201_with_default_role(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "ash@geekbaku.dev"
        assert [r["name"] for r in body["roles"]] == ["user"]

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

        response = await client.post(
            "/api/v1/auth/register",
            json={**REGISTER_PAYLOAD, "username": "someone_else"},
        )

        assert response.status_code == 409

    async def test_register_weak_password_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "password": "weak"}
        )

        assert response.status_code == 422


class TestLogin:
    async def test_login_returns_tokens(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]["token_type"] == "bearer"
        assert body["refresh_token"]

    async def test_login_wrong_password_returns_401(self, client: AsyncClient) -> None:
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": "wrong-password"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_error"

    async def test_login_unknown_email_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@geekbaku.dev", "password": "whatever123A"}
        )

        assert response.status_code == 401

    async def test_login_brute_force_protection_blocks_after_failures(
        self, client: AsyncClient
    ) -> None:
        await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
        wrong = {"email": REGISTER_PAYLOAD["email"], "password": "wrong-password"}

        for _ in range(5):
            await client.post("/api/v1/auth/login", json=wrong)

        response = await client.post("/api/v1/auth/login", json=wrong)

        assert response.status_code == 429


class TestMe:
    async def test_me_requires_bearer_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401  # HTTPBearer sin header

    async def test_me_returns_current_user(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        access_token = auth["access_token"]["value"]  # type: ignore[index]

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == "ash@geekbaku.dev"

    async def test_me_rejects_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401


class TestProfileAndSettings:
    async def test_update_profile(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        access_token = auth["access_token"]["value"]  # type: ignore[index]

        response = await client.patch(
            "/api/v1/auth/profile",
            json={"display_name": "Ash"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert response.json()["profile"]["display_name"] == "Ash"

    async def test_update_settings(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        access_token = auth["access_token"]["value"]  # type: ignore[index]

        response = await client.patch(
            "/api/v1/auth/settings",
            json={"theme": "dark"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert response.json()["settings"]["theme"] == "dark"


class TestRefreshAndLogout:
    async def test_refresh_rotates_token(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        refresh_token = auth["refresh_token"]

        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert response.json()["refresh_token"] != refresh_token

    async def test_reusing_rotated_refresh_token_returns_401(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        refresh_token = auth["refresh_token"]
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 401

    async def test_logout_revokes_refresh_token(self, client: AsyncClient) -> None:
        auth = await _register_and_login(client)
        refresh_token = auth["refresh_token"]

        logout_response = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": refresh_token}
        )
        assert logout_response.status_code == 204

        refresh_response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 401
