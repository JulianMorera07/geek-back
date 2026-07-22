"""Mappers del módulo de providers: primitivos/DTOs <-> Value Objects de dominio."""

from __future__ import annotations

from geekbaku.application.providers.dto import ExternalReferenceDTO, SearchResultDTO
from geekbaku.domain.providers.value_objects import ExternalReference, ProviderId, SearchResult


def parse_provider_id(value: str) -> ProviderId:
    return ProviderId(value)


def parse_external_reference(dto: ExternalReferenceDTO) -> ExternalReference:
    return ExternalReference(
        provider_id=parse_provider_id(dto.provider_id), external_id=dto.external_id
    )


def external_reference_to_dto(reference: ExternalReference) -> ExternalReferenceDTO:
    return ExternalReferenceDTO(
        provider_id=str(reference.provider_id), external_id=reference.external_id
    )


def search_result_to_dto(result: SearchResult) -> SearchResultDTO:
    return SearchResultDTO(
        provider_id=str(result.reference.provider_id),
        external_id=result.reference.external_id,
        title=result.title,
        thumbnail_url=result.thumbnail.url.value if result.thumbnail else None,
        anime_type=str(result.anime_type) if result.anime_type else None,
        year=result.year,
    )
