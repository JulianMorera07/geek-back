"""Caso de uso: PATCH /auth/profile. Campos `None` en el command dejan el
valor actual sin cambios (PATCH semántico, no PUT) — `Profile` se
reemplaza entero (ver `domain.identity.value_objects.Profile`) pero con
los campos no enviados copiados del `Profile` vigente.
"""

from __future__ import annotations

from geekbaku.application.identity.dto import UpdateProfileCommand, UserDTO
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import parse_user_id, user_to_dto
from geekbaku.application.identity.ports import IdentityUnitOfWork
from geekbaku.domain.identity.exceptions import UserNotFoundError
from geekbaku.domain.identity.value_objects import Profile


class UpdateProfile:
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: UpdateProfileCommand) -> UserDTO:
        user = await self._uow.users.get_by_id(parse_user_id(command.user_id))
        if user is None:
            raise UserNotFoundError(f"No existe el usuario {command.user_id}.")

        current = user.profile
        user.update_profile(
            Profile(
                display_name=(
                    command.display_name
                    if command.display_name is not None
                    else current.display_name
                ),
                avatar_url=(
                    command.avatar_url if command.avatar_url is not None else current.avatar_url
                ),
                bio=command.bio if command.bio is not None else current.bio,
            )
        )
        await self._uow.users.update(user)

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        return user_to_dto(user, roles=roles, permissions=permissions)
