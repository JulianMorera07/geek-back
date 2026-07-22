"""EpisodeController: detalle de un episodio, independiente de su Anime."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geekbaku.application.catalog.use_cases.get_episode_by_id import GetEpisodeById
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.catalog_schemas import EpisodeSchema

router = APIRouter(tags=["episodes"])


@router.get(
    "/episodes/{episode_id}",
    summary="Obtener el detalle de un Episode por id",
    responses={404: {"description": "No existe un Episode con ese id."}},
)
async def get_episode(
    episode_id: str,
    use_case: GetEpisodeById = Depends(deps.get_episode_by_id_use_case),
) -> EpisodeSchema:
    result = await use_case.execute(episode_id)
    return EpisodeSchema.model_validate(result, from_attributes=True)
