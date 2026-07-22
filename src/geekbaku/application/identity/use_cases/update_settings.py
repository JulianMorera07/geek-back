"""Caso de uso: PATCH /auth/settings. Misma semántica PATCH que
`UpdateProfile`: campos `None` conservan el valor actual."""

from __future__ import annotations

from geekbaku.application.identity.dto import UpdateSettingsCommand, UserDTO
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import parse_user_id, user_to_dto
from geekbaku.application.identity.ports import IdentityUnitOfWork
from geekbaku.domain.identity.exceptions import UserNotFoundError
from geekbaku.domain.identity.value_objects import UserSettings


class UpdateSettings:
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: UpdateSettingsCommand) -> UserDTO:
        user = await self._uow.users.get_by_id(parse_user_id(command.user_id))
        if user is None:
            raise UserNotFoundError(f"No existe el usuario {command.user_id}.")

        current = user.settings
        user.update_settings(
            UserSettings(
                language=command.language if command.language is not None else current.language,
                theme=command.theme if command.theme is not None else current.theme,
                notifications_enabled=(
                    command.notifications_enabled
                    if command.notifications_enabled is not None
                    else current.notifications_enabled
                ),
            )
        )
        await self._uow.users.update(user)

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        return user_to_dto(user, roles=roles, permissions=permissions)
