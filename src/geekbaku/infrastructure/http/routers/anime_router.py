"""AnimeController: listado/detalle del catálogo interno y sus episodios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from geekbaku.application.catalog.dto import ListCatalogQuery
from geekbaku.application.catalog.use_cases.get_anime_by_id import GetAnimeById
from geekbaku.application.catalog.use_cases.get_anime_episodes import GetAnimeEpisodes
from geekbaku.application.catalog.use_cases.list_catalog import ListCatalog
from geekbaku.application.ingestion.dto import IngestAnimeCommand
from geekbaku.application.ingestion.use_cases.ingest_anime_from_provider import (
    IngestAnimeFromProvider,
)
from geekbaku.infrastructure.http import deps
from geekbaku.infrastructure.http.schemas.catalog_schemas import (
    AnimeDetailSchema,
    AnimeSummarySchema,
    EpisodeSchema,
)
from geekbaku.infrastructure.http.schemas.common_schemas import PageSchema

router = APIRouter(tags=["anime"])


@router.get(
    "/anime",
    summary="Listar el catálogo interno de Anime",
    description=(
        "Devuelve una página de Anime del catálogo interno, con filtros "
        "opcionales por tipo, estado, género, estudio, productor, tag y "
        "texto libre."
    ),
    response_description="Página de resultados del catálogo.",
)
async def list_anime(
    status: str | None = None,
    type: str | None = None,
    genre_id: str | None = None,
    studio_id: str | None = None,
    producer_id: str | None = None,
    tag_id: str | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    use_case: ListCatalog = Depends(deps.get_list_catalog_use_case),
) -> PageSchema[AnimeSummarySchema]:
    result = await use_case.execute(
        ListCatalogQuery(
            status=status,
            type=type,
            genre_id=genre_id,
            studio_id=studio_id,
            producer_id=producer_id,
            tag_id=tag_id,
            search_text=q,
            page=page,
            page_size=page_size,
        )
    )
    return PageSchema[AnimeSummarySchema](
        items=tuple(
            AnimeSummarySchema.model_validate(item, from_attributes=True)
            for item in result.items
        ),
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/anime/{anime_id}",
    summary="Obtener el detalle de un Anime por id",
    responses={404: {"description": "No existe un Anime con ese id."}},
)
async def get_anime(
    anime_id: str,
    use_case: GetAnimeById = Depends(deps.get_anime_by_id_use_case),
) -> AnimeDetailSchema:
    result = await use_case.execute(anime_id)
    return AnimeDetailSchema.model_validate(result, from_attributes=True)


@router.get(
    "/anime/{anime_id}/episodes",
    summary="Listar todos los episodios de un Anime",
    description="Aplana los episodios de todas las Seasons, ordenados por temporada y episodio.",
    responses={404: {"description": "No existe un Anime con ese id."}},
)
async def get_anime_episodes(
    anime_id: str,
    use_case: GetAnimeEpisodes = Depends(deps.get_anime_episodes_use_case),
) -> list[EpisodeSchema]:
    episodes = await use_case.execute(anime_id)
    return [EpisodeSchema.model_validate(e, from_attributes=True) for e in episodes]


@router.get(
    "/anime/external/{provider_id}/{external_id}",
    summary="Obtener (e ingerir si hace falta) el detalle de un Anime desde un resultado externo",
    description=(
        "Puente entre un resultado de /search, /latest o /popular (que vienen de un "
        "provider externo, ej. AnimeFLV) y el catálogo interno. Si el Anime ya fue "
        "ingerido antes, devuelve la copia interna existente. Si no, lo trae del "
        "provider (detalle + episodios + fuentes de streaming), lo persiste como "
        "Anime/Episode/StreamingSource, y devuelve el resultado ya listo para "
        "reproducir vía Playback Engine."
    ),
    responses={404: {"description": "El provider no tiene un anime con ese external_id."}},
)
async def get_or_ingest_anime_by_external_reference(
    provider_id: str,
    external_id: str,
    use_case: IngestAnimeFromProvider = Depends(deps.get_ingest_anime_from_provider_use_case),
) -> AnimeDetailSchema:
    result = await use_case.execute(
        IngestAnimeCommand(provider_id=provider_id, external_id=external_id)
    )
    return AnimeDetailSchema.model_validate(result, from_attributes=True)
