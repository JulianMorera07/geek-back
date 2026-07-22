"""ProviderController: estado público de los providers registrados en el
Provider Framework — nunca expone credenciales/URLs internas del adapter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geekbaku.application.providers.use_cases.list_providers import ListProviders
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.provider_schemas import ProviderInfoSchema

router = APIRouter(tags=["providers"])


@router.get(
    "/providers",
    summary="Listar los providers registrados",
    description=(
        "Configuración administrativa (habilitado, prioridad) y estado "
        "observacional en vivo (salud, estadísticas) de cada provider "
        "registrado en el Provider Framework."
    ),
)
async def list_providers(
    use_case: ListProviders = Depends(deps.get_list_providers_use_case),
) -> list[ProviderInfoSchema]:
    providers = await use_case.execute()
    return [ProviderInfoSchema.model_validate(p, from_attributes=True) for p in providers]
