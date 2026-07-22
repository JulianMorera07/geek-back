"""CatalogController: estructura de navegación del catálogo interno
(tipos, estados, géneros, estudios, productores, tags) para armar filtros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geekbaku.application.catalog.use_cases.get_catalog_facets import GetCatalogFacets
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.catalog_schemas import CatalogFacetsSchema

router = APIRouter(tags=["catalog"])


@router.get(
    "/catalog",
    summary="Obtener la estructura de navegación del catálogo",
    description=(
        "Todo lo que un frontend necesita para armar filtros de búsqueda: "
        "tipos y estados disponibles (enumeraciones cerradas) más géneros, "
        "estudios, productores y tags ya creados (catálogos abiertos)."
    ),
)
async def get_catalog(
    use_case: GetCatalogFacets = Depends(deps.get_catalog_facets_use_case),
) -> CatalogFacetsSchema:
    facets = await use_case.execute()
    return CatalogFacetsSchema.model_validate(facets, from_attributes=True)
