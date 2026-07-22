"""Schemas Pydantic genéricos, reusados por varios routers."""

from __future__ import annotations

from pydantic import BaseModel


class PageSchema[T](BaseModel):
    """Espejo de `application.common.pagination.Page`."""

    items: tuple[T, ...]
    total: int
    page: int
    page_size: int


class ErrorDetailSchema(BaseModel):
    code: str
    message: str


class ErrorResponseSchema(BaseModel):
    """Forma de cualquier respuesta de error de la API (ver
    `infrastructure/http/exception_handlers.py`), documentada acá para que
    OpenAPI describa el shape de error de forma consistente en todos los
    endpoints.
    """

    error: ErrorDetailSchema
