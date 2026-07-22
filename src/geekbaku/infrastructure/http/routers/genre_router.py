"""GenreController: catálogo abierto de géneros del catálogo interno."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geekbaku.application.catalog.use_cases.get_genre import GetGenre
from geekbaku.application.catalog.use_cases.list_genres import ListGenres
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.catalog_schemas import GenreSchema

router = APIRouter(tags=["genres"])


@router.get("/genres", summary="Listar todos los géneros")
async def list_genres(
    use_case: ListGenres = Depends(deps.get_list_genres_use_case),
) -> list[GenreSchema]:
    genres = await use_case.execute()
    return [GenreSchema.model_validate(g, from_attributes=True) for g in genres]


@router.get(
    "/genres/{genre_id}",
    summary="Obtener un género por id",
    responses={404: {"description": "No existe un género con ese id."}},
)
async def get_genre(
    genre_id: str,
    use_case: GetGenre = Depends(deps.get_genre_use_case),
) -> GenreSchema:
    genre = await use_case.execute(genre_id)
    return GenreSchema.model_validate(genre, from_attributes=True)
