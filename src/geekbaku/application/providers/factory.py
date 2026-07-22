"""Provider Factory: construye instancias de `ProviderPort` sin acoplar el
resto del sistema a ninguna clase concreta de adapter.

Un "kind" (ej. `"provider_a"`) se registra junto con un constructor
(`ProviderConfiguration -> ProviderPort`). El composition root, en un sprint
futuro cuando existan adapters concretos, hará
`factory.register_constructor("provider_a", ProviderAAdapter)` y luego
`factory.create("provider_a", configuration)` para obtener la instancia que
se pasa a `ProviderRegistry.register`. Este sprint no registra ningún
constructor real: solo la fábrica vacía, lista para usarse.
"""

from __future__ import annotations

from collections.abc import Callable

from geekbaku.application.providers.ports import ProviderPort
from geekbaku.domain.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
)
from geekbaku.domain.providers.value_objects import ProviderConfiguration

ProviderConstructor = Callable[[ProviderConfiguration], ProviderPort]


class ProviderFactory:
    """Registro de constructores de `ProviderPort`, indexados por "kind"."""

    def __init__(self) -> None:
        self._constructors: dict[str, ProviderConstructor] = {}

    def register_constructor(self, kind: str, constructor: ProviderConstructor) -> None:
        if kind in self._constructors:
            raise ProviderAlreadyRegisteredError(
                f"Ya hay un constructor registrado para el kind '{kind}'."
            )
        self._constructors[kind] = constructor

    def unregister_constructor(self, kind: str) -> None:
        if kind not in self._constructors:
            raise ProviderNotFoundError(f"No hay constructor registrado para el kind '{kind}'.")
        del self._constructors[kind]

    def create(self, kind: str, configuration: ProviderConfiguration) -> ProviderPort:
        try:
            constructor = self._constructors[kind]
        except KeyError:
            raise ProviderNotFoundError(
                f"No hay constructor registrado para el kind '{kind}'."
            ) from None
        return constructor(configuration)

    def list_kinds(self) -> tuple[str, ...]:
        return tuple(self._constructors.keys())
