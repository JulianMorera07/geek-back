"""Caso de uso: GET /auth/me. Recibe la `Identity` ya decodificada del
AccessToken (ver `infrastructure.http.deps.get_current_identity`) y carga
el `User` fresco — el token puede tener roles/permisos ligeramente
desactualizados si cambiaron después de emitirlo; `/me` siempre refleja el
estado actual persistido.
"""

from __future__ import annotations

from geekbaku.application.identity.dto import UserDTO
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import user_to_dto
from geekbaku.application.identity.ports import IdentityUnitOfWork
from geekbaku.domain.identity.exceptions import InactiveUserError, UserNotFoundError
from geekbaku.domain.identity.value_objects import UserId


class GetCurrentUser:
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, user_id: UserId) -> UserDTO:
        user = await self._uow.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"No existe el usuario {user_id}.")
        if not user.is_active:
            raise InactiveUserError(f"El usuario {user.id} está desactivado.")

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        return user_to_dto(user, roles=roles, permissions=permissions)
