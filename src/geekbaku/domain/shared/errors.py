"""Excepciones base del dominio.

Todas las excepciones de dominio (en cualquier módulo bajo `domain/`) deben
heredar de `DomainError`. La traducción de estas excepciones a respuestas
HTTP ocurre exclusivamente en `infrastructure/http/exception_handlers.py`,
nunca dentro de un caso de uso.
"""


class DomainError(Exception):
    """Excepción base para cualquier violación de una regla de dominio."""


class NotFoundError(DomainError):
    """Se pide una entidad/agregado que no existe."""


class ConflictError(DomainError):
    """Una operación viola una invariante de unicidad o de estado."""


class ValidationError(DomainError):
    """Un valor no cumple una regla de validación de dominio."""
