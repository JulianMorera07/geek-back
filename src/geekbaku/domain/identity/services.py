"""Domain services del módulo de identidad.

Ambos son puros (sin I/O): `PasswordPolicy` valida contraseñas en texto
plano ANTES de hashearlas (hashear es infraestructura); `AuthorizationService`
decide RBAC + policies a partir de una `Identity` ya resuelta, sin volver a
consultar ningún repositorio.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from geekbaku.domain.identity.exceptions import (
    InactiveUserError,
    PermissionDeniedError,
    WeakPasswordError,
)
from geekbaku.domain.identity.value_objects import Identity

#: Una policy es un predicado adicional sobre la `Identity` ya autenticada
#: (ej. "solo el dueño del recurso", "solo fuera de horario de mantenimiento").
#: Se evalúa DESPUÉS de que el chequeo RBAC básico (resource:action) pasa —
#: es un AND, nunca reemplaza al permiso, lo restringe más.
Policy = Callable[[Identity], bool]


class PasswordPolicy:
    """Reglas de fortaleza de contraseña. Deliberadamente simple y
    explícita (sin dependencias externas de scoring) para que la regla
    sea auditable a simple vista.
    """

    MIN_LENGTH = 8

    @classmethod
    def validate(cls, password: str) -> None:
        if len(password) < cls.MIN_LENGTH:
            raise WeakPasswordError(
                f"La contraseña debe tener al menos {cls.MIN_LENGTH} caracteres."
            )
        if not any(c.isupper() for c in password):
            raise WeakPasswordError("La contraseña debe incluir al menos una mayúscula.")
        if not any(c.islower() for c in password):
            raise WeakPasswordError("La contraseña debe incluir al menos una minúscula.")
        if not any(c.isdigit() for c in password):
            raise WeakPasswordError("La contraseña debe incluir al menos un dígito.")


class AuthorizationService:
    """RBAC + policies sobre una `Identity` ya resuelta (claims del
    `AccessToken`, ver `domain.identity.value_objects.Identity`).
    """

    @staticmethod
    def has_permission(identity: Identity, resource: str, action: str) -> bool:
        return identity.has_permission(resource, action)

    @staticmethod
    def authorize(
        identity: Identity,
        resource: str,
        action: str,
        *,
        policies: Sequence[Policy] = (),
    ) -> None:
        """Levanta `PermissionDeniedError`/`InactiveUserError` si el acceso
        no está permitido; no devuelve nada si está permitido.
        """
        if not identity.is_active:
            raise InactiveUserError(f"El usuario {identity.user_id} está desactivado.")
        if not AuthorizationService.has_permission(identity, resource, action):
            raise PermissionDeniedError(
                f"La identidad {identity.user_id} no tiene el permiso '{resource}:{action}'."
            )
        for policy in policies:
            if not policy(identity):
                raise PermissionDeniedError(
                    f"Una policy denegó el acceso a '{resource}:{action}' "
                    f"para {identity.user_id}."
                )


__all__ = ["AuthorizationService", "PasswordPolicy", "Policy"]
