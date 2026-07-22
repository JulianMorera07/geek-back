"""Excepciones propias de la capa de aplicación de `providers`.

Separadas de `geekbaku.domain.providers.exceptions` porque este sprint no
modifica el dominio: `ProviderCircuitOpenError` es un concepto de
resiliencia introducido en Sprint 5 (`CircuitBreaker`), y se define aquí en
vez de ahí para respetar esa restricción. Un sprint futuro podría
reconciliar la ubicación de todas las excepciones de providers en un único
lugar si se revisita el dominio.
"""

from __future__ import annotations

from geekbaku.domain.shared.errors import DomainError


class ProviderCircuitOpenError(DomainError):
    """El circuit breaker del provider está `OPEN`: no se intentó la
    llamada real. Ver `application/providers/circuit_breaker.py`.
    """
