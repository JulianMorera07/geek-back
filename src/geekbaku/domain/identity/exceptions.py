"""Excepciones del módulo de identidad.

Todas heredan de `DomainError` (`domain.shared.errors`), pero el módulo
introduce dos bases nuevas que `exception_handlers.py` traduce a códigos
HTTP que ningún sprint anterior necesitaba: `AuthenticationError` (401 —
credenciales/token ausentes, inválidos o expirados) y
`PermissionDeniedError` (403 — identidad válida pero sin el permiso
requerido). `TooManyAttemptsError` (429) cubre la protección de fuerza
bruta.
"""

from __future__ import annotations

from geekbaku.domain.shared.errors import ConflictError, DomainError, NotFoundError, ValidationError


class IdentityError(DomainError):
    """Base de cualquier error del módulo de identidad."""


class AuthenticationError(IdentityError):
    """401: no se pudo establecer quién es el llamador."""


class PermissionDeniedError(IdentityError):
    """403: la identidad es válida pero no tiene el permiso requerido."""


class TooManyAttemptsError(IdentityError):
    """429: se superó el límite de intentos permitido (fuerza bruta / rate limit)."""


class InvalidCredentialsError(AuthenticationError):
    """Email/username y contraseña no coinciden (o el usuario no existe).

    Deliberadamente el mismo mensaje/tipo en ambos casos: no debe ser
    posible enumerar emails registrados observando la respuesta de error.
    """


class UserAlreadyExistsError(ConflictError):
    """Ya existe un `User` con ese email o username."""


class UserNotFoundError(NotFoundError):
    pass


class InactiveUserError(AuthenticationError):
    """El usuario existe pero está desactivado."""


class WeakPasswordError(ValidationError):
    """La contraseña no cumple la `PasswordPolicy`."""


class RoleNotFoundError(NotFoundError):
    pass


class RoleAlreadyExistsError(ConflictError):
    pass


class PermissionNotFoundError(NotFoundError):
    pass


class SessionNotFoundError(NotFoundError):
    pass


class SessionExpiredError(AuthenticationError):
    pass


class SessionRevokedError(AuthenticationError):
    pass


class RefreshTokenNotFoundError(AuthenticationError):
    """401, no 404: un refresh token inexistente no debe distinguirse de uno
    inválido/expirado desde afuera."""


class RefreshTokenExpiredError(AuthenticationError):
    pass


class RefreshTokenRevokedError(AuthenticationError):
    pass


class RefreshTokenReusedError(AuthenticationError):
    """Se intentó usar un refresh token que ya había sido rotado.

    Señal de robo de token: quien detecta esto debe revocar toda la cadena
    de tokens de la sesión, no solo rechazar el pedido (ver
    `RefreshAccessToken`).
    """


class AuthenticationProviderNotFoundError(AuthenticationError):
    """No hay ningún `AuthenticationProvider` registrado con ese id."""


class AuthenticationProviderAlreadyRegisteredError(ConflictError):
    pass


__all__ = [
    "AuthenticationError",
    "AuthenticationProviderAlreadyRegisteredError",
    "AuthenticationProviderNotFoundError",
    "IdentityError",
    "InactiveUserError",
    "InvalidCredentialsError",
    "PermissionDeniedError",
    "PermissionNotFoundError",
    "RefreshTokenExpiredError",
    "RefreshTokenNotFoundError",
    "RefreshTokenReusedError",
    "RefreshTokenRevokedError",
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "SessionExpiredError",
    "SessionNotFoundError",
    "SessionRevokedError",
    "TooManyAttemptsError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "WeakPasswordError",
]
