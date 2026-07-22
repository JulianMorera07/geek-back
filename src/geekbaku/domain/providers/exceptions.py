"""Excepciones de dominio del módulo de providers."""

from __future__ import annotations

from geekbaku.domain.shared.errors import ConflictError, DomainError, NotFoundError


class ProviderNotFoundError(NotFoundError):
    """No hay ningún provider registrado con ese `ProviderId`."""


class ProviderAlreadyRegisteredError(ConflictError):
    """Ya existe un provider registrado con ese `ProviderId`."""


class ProviderCapabilityNotSupportedError(DomainError):
    """El provider no soporta la capacidad solicitada (ver `ProviderMetadata`)."""


class ProviderRateLimitExceededError(DomainError):
    """Se excedió el límite de peticiones configurado (`RateLimitConfig`) para
    el provider antes de siquiera intentar la llamada.
    """


class ProviderRequestError(DomainError):
    """La llamada al provider falló (timeout, error de parsing, HTTP, etc.).

    El `ProviderManager` envuelve cualquier excepción no controlada que un
    `ProviderPort` concreto lance en esta excepción, para que la capa de
    aplicación tenga un único tipo estable que manejar sin importar qué
    proveedor específico falló ni por qué.
    """
