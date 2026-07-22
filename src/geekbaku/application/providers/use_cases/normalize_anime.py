"""Caso de uso: normalizar información cruda de un provider.

Expone explícitamente como caso de uso la capa anti-corrupción que traduce
`ProviderAnimeDTO` (vocabulario propio de un proveedor) a `NormalizedAnimeDTO`
(vocabulario de dominio de GeekBaku). `GetProviderAnimeDetail` ya la invoca
internamente al pedir un detalle; este caso de uso permite normalizar datos
obtenidos por otra vía (ej. un lote ya descargado) sin pasar de nuevo por el
Provider Engine.
"""

from __future__ import annotations

from geekbaku.application.providers.dto import NormalizedAnimeDTO, ProviderAnimeDTO
from geekbaku.application.providers.normalizers import to_normalized_anime


class NormalizeAnime:
    def execute(self, provider_anime: ProviderAnimeDTO) -> NormalizedAnimeDTO:
        return to_normalized_anime(provider_anime)
