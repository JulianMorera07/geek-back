"""SearchController: búsqueda/descubrimiento distribuido entre providers
(Aggregation Engine) — nunca contra el catálogo interno.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from geekbaku.application.aggregation.use_cases.get_aggregated_latest import GetAggregatedLatest
from geekbaku.application.aggregation.use_cases.get_aggregated_popular import (
    GetAggregatedPopular,
)
from geekbaku.application.aggregation.use_cases.search_aggregated_anime import (
    SearchAggregatedAnime,
)
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.search_schemas import AggregatedSearchResultSchema

router = APIRouter(tags=["search"])


def _parse_provider_ids(provider_ids: str | None) -> tuple[str, ...] | None:
    if provider_ids is None:
        return None
    return tuple(p.strip() for p in provider_ids.split(",") if p.strip())


@router.get(
    "/search",
    summary="Búsqueda distribuida entre providers",
    description=(
        "Consulta en paralelo a todos los providers registrados (o a los "
        "indicados en `provider_ids`), deduplica resultados del mismo "
        "anime y devuelve una única lista ordenada."
    ),
)
async def search_anime(
    q: str = Query(..., min_length=1, examples=["shingeki no kyojin"]),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    provider_ids: str | None = Query(
        default=None, description="Lista separada por comas, ej. 'jikan,otro-provider'."
    ),
    use_case: SearchAggregatedAnime = Depends(deps.get_search_aggregated_anime_use_case),
) -> list[AggregatedSearchResultSchema]:
    results = await use_case.execute(q, page, page_size, _parse_provider_ids(provider_ids))
    return [AggregatedSearchResultSchema.model_validate(r, from_attributes=True) for r in results]


@router.get(
    "/latest",
    summary="Últimos Anime agregados entre providers",
)
async def get_latest(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    provider_ids: str | None = Query(default=None),
    use_case: GetAggregatedLatest = Depends(deps.get_aggregated_latest_use_case),
) -> list[AggregatedSearchResultSchema]:
    results = await use_case.execute(page, page_size, _parse_provider_ids(provider_ids))
    return [AggregatedSearchResultSchema.model_validate(r, from_attributes=True) for r in results]


@router.get(
    "/popular",
    summary="Anime más populares entre providers",
)
async def get_popular(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    provider_ids: str | None = Query(default=None),
    use_case: GetAggregatedPopular = Depends(deps.get_aggregated_popular_use_case),
) -> list[AggregatedSearchResultSchema]:
    results = await use_case.execute(page, page_size, _parse_provider_ids(provider_ids))
    return [AggregatedSearchResultSchema.model_validate(r, from_attributes=True) for r in results]
