"""Resuelve roles y permisos de un `User` — repetido por casi todos los
casos de uso (login, register, get_current_user, update_profile/settings),
factorizado acá para no duplicar la composición `role_ids -> Roles ->
permission_ids -> Permissions`.
"""

from __future__ import annotations

from geekbaku.application.identity.ports import IdentityUnitOfWork
from geekbaku.domain.identity.entities import Permission, Role, User


async def load_roles_and_permissions(
    uow: IdentityUnitOfWork, user: User
) -> tuple[list[Role], list[Permission]]:
    roles = await uow.roles.list_by_ids(user.role_ids)
    permission_ids = {pid for role in roles for pid in role.permission_ids}
    permissions = await uow.permissions.list_by_ids(permission_ids)
    return roles, permissions


__all__ = ["load_roles_and_permissions"]
