"""Mappers del módulo de identidad: primitivos <-> Value Objects de
dominio, y entidades -> DTOs. Cualquier error de parseo se traduce a
`ValidationError` de dominio (misma convención que `application.catalog.mappers`).
"""

from __future__ import annotations

from uuid import UUID

from geekbaku.application.identity.dto import (
    PermissionDTO,
    ProfileDTO,
    RoleDTO,
    UserDTO,
    UserSettingsDTO,
)
from geekbaku.domain.identity.entities import Permission, Role, User
from geekbaku.domain.identity.value_objects import Identity, PermissionId, RoleId, UserId
from geekbaku.domain.shared.errors import ValidationError


def parse_user_id(value: str) -> UserId:
    try:
        return UserId(UUID(value))
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un UserId válido.") from exc


def parse_role_id(value: str) -> RoleId:
    try:
        return RoleId(UUID(value))
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un RoleId válido.") from exc


def parse_permission_id(value: str) -> PermissionId:
    try:
        return PermissionId(UUID(value))
    except ValueError as exc:
        raise ValidationError(f"'{value}' no es un PermissionId válido.") from exc


def role_to_dto(role: Role) -> RoleDTO:
    return RoleDTO(id=str(role.id), name=role.name, is_system=role.is_system)


def permission_to_dto(permission: Permission) -> PermissionDTO:
    return PermissionDTO(
        id=str(permission.id),
        resource=permission.resource,
        action=permission.action,
        description=permission.description,
    )


def user_to_dto(user: User, roles: list[Role], permissions: list[Permission]) -> UserDTO:
    return UserDTO(
        id=str(user.id),
        email=str(user.email),
        username=str(user.username),
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=tuple(role_to_dto(r) for r in roles),
        permissions=tuple(sorted({p.key for p in permissions})),
        profile=ProfileDTO(
            display_name=user.profile.display_name,
            avatar_url=user.profile.avatar_url,
            bio=user.profile.bio,
        ),
        settings=UserSettingsDTO(
            language=user.settings.language,
            theme=user.settings.theme,
            notifications_enabled=user.settings.notifications_enabled,
        ),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def build_identity(user: User, roles: list[Role], permissions: list[Permission]) -> Identity:
    return Identity(
        user_id=user.id,
        email=str(user.email),
        roles=frozenset(r.name for r in roles),
        permissions=frozenset(p.key for p in permissions),
        is_active=user.is_active,
    )


__all__ = [
    "build_identity",
    "parse_permission_id",
    "parse_role_id",
    "parse_user_id",
    "permission_to_dto",
    "role_to_dto",
    "user_to_dto",
]
