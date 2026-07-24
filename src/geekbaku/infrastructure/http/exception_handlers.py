import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from geekbaku.domain.identity.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    TooManyAttemptsError,
)
from geekbaku.domain.shared.errors import ConflictError, DomainError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Punto único de traducción de errores de dominio a respuestas HTTP.

    Starlette despacha por el tipo más específico registrado en el MRO de la
    excepción levantada, así que alcanza con registrar las 3 subclases base
    de `DomainError` (`NotFoundError`, `ConflictError`, `ValidationError`) +
    las 3 que introduce el módulo de identidad (`AuthenticationError` → 401,
    `PermissionDeniedError` → 403, `TooManyAttemptsError` → 429) + un
    fallback para cualquier otra `DomainError` — ninguna excepción concreta
    (`AnimeNotFoundError`, `InvalidCredentialsError`, ...) necesita su
    propio handler.
    """

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, "not_found", str(exc))

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "conflict", str(exc))

    @app.exception_handler(ValidationError)
    async def validation_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        _request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "authentication_error", str(exc))

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(
        _request: Request, exc: PermissionDeniedError
    ) -> JSONResponse:
        return _error_response(status.HTTP_403_FORBIDDEN, "permission_denied", str(exc))

    @app.exception_handler(TooManyAttemptsError)
    async def too_many_attempts_handler(
        _request: Request, exc: TooManyAttemptsError
    ) -> JSONResponse:
        return _error_response(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts", str(exc))

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(status.HTTP_400_BAD_REQUEST, "domain_error", str(exc))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "An unexpected error occurred.",
        )
