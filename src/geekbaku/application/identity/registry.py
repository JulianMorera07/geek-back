"""Authentication Provider Registry.

Deliberadamente una implementación propia, independiente de
`application.providers.registry.ProviderRegistry` (Provider Framework):
identidad debe poder evolucionar sin acoplarse a, ni ser tocada por,
cambios del Provider Framework, y viceversa — son dos ejes de
extensibilidad completamente distintos (de dónde sale el catálogo vs.
quién es el usuario) que solo comparten la forma del patrón, no código.
"""

from __future__ import annotations

from geekbaku.application.identity.ports import AuthenticationProvider
from geekbaku.domain.identity.exceptions import (
    AuthenticationProviderAlreadyRegisteredError,
    AuthenticationProviderNotFoundError,
)


class AuthenticationProviderRegistry:
    """Registro en memoria de estrategias de autenticación. Agregar una
    estrategia nueva (OAuth, magic-link, ...) es: implementar
    `AuthenticationProvider` en infraestructura y llamar `.register(...)`
    en el composition root — cero cambios en dominio o casos de uso.
    """

    def __init__(self) -> None:
        self._providers: dict[str, AuthenticationProvider] = {}

    def register(self, provider: AuthenticationProvider) -> None:
        if provider.provider_id in self._providers:
            raise AuthenticationProviderAlreadyRegisteredError(
                f"Ya hay un AuthenticationProvider registrado con id '{provider.provider_id}'."
            )
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> AuthenticationProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise AuthenticationProviderNotFoundError(
                f"No hay ningún AuthenticationProvider registrado con id '{provider_id}'."
            ) from exc

    def __contains__(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def list_provider_ids(self) -> tuple[str, ...]:
        return tuple(self._providers.keys())


__all__ = ["AuthenticationProviderRegistry"]
