"""Caso de uso: registrar un nuevo usuario con credenciales de tipo
'password'. Asigna el rol por defecto ('user', sembrado por el
`IdentityUnitOfWork` — ver `infrastructure.identity.repositories`)."""

from __future__ import annotations

from geekbaku.application.identity.dto import RegisterUserCommand, UserDTO
from geekbaku.application.identity.loaders import load_roles_and_permissions
from geekbaku.application.identity.mappers import user_to_dto
from geekbaku.application.identity.ports import IdentityUnitOfWork, PasswordHasher
from geekbaku.domain.identity.entities import Credential, User
from geekbaku.domain.identity.exceptions import RoleNotFoundError, UserAlreadyExistsError
from geekbaku.domain.identity.services import PasswordPolicy
from geekbaku.domain.identity.value_objects import CredentialId, Email, UserId, Username

DEFAULT_ROLE_NAME = "user"


class RegisterUser:
    def __init__(self, uow: IdentityUnitOfWork, password_hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = password_hasher

    async def execute(self, command: RegisterUserCommand) -> UserDTO:
        email = Email(command.email)
        username = Username(command.username)
        PasswordPolicy.validate(command.password)

        if await self._uow.users.get_by_email(str(email)) is not None:
            raise UserAlreadyExistsError(f"Ya existe un usuario con el email '{email}'.")
        if await self._uow.users.get_by_username(str(username)) is not None:
            raise UserAlreadyExistsError(f"Ya existe un usuario con el username '{username}'.")

        default_role = await self._uow.roles.get_by_name(DEFAULT_ROLE_NAME)
        if default_role is None:
            raise RoleNotFoundError(f"No existe el rol por defecto '{DEFAULT_ROLE_NAME}'.")

        user = User(id=UserId.new(), email=email, username=username, role_ids={default_role.id})
        await self._uow.users.add(user)

        credential = Credential(
            id=CredentialId.new(),
            user_id=user.id,
            provider_id="password",
            secret_hash=self._hasher.hash(command.password),
        )
        await self._uow.credentials.add(credential)

        roles, permissions = await load_roles_and_permissions(self._uow, user)
        return user_to_dto(user, roles=roles, permissions=permissions)
