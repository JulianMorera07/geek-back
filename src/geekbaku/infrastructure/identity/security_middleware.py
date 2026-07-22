"""Middlewares de seguridad transversal del módulo de identidad.

`SecurityHeadersMiddleware` aplica a TODA la app (headers de seguridad son
higiene general, no algo específico de `/auth`). `AuthRateLimitMiddleware`
solo limita `/api/v1/auth/*`: es Rate Limiting a nivel de transporte
(peticiones por IP en una ventana), complementario al `BruteForceGuard`
de `LoginUser` (que limita intentos fallidos por email+IP) — dos defensas
distintas para dos amenazas distintas (flood vs. credential stuffing).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Ventana fija en memoria: `max_requests` por IP cada `window_seconds`,
    aplicado solo a rutas bajo `path_prefix`.
    """

    def __init__(
        self,
        app: object,
        *,
        path_prefix: str = "/api/v1/auth",
        max_requests: int = 30,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._path_prefix = path_prefix
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, tuple[int, float]] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not request.url.path.startswith(self._path_prefix):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        count, window_started_at = self._hits.get(client_ip, (0, now))
        if now - window_started_at >= self._window_seconds:
            count, window_started_at = 0, now
        count += 1
        self._hits[client_ip] = (count, window_started_at)

        if count > self._max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "too_many_requests",
                        "message": "Demasiadas peticiones. Intentá de nuevo más tarde.",
                    }
                },
            )
        return await call_next(request)


__all__ = ["AuthRateLimitMiddleware", "SecurityHeadersMiddleware"]
