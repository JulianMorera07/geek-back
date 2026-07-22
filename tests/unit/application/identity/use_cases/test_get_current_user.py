import pytest

from geekbaku.application.identity.dto import RegisterUserCommand
from geekbaku.application.identity.mappers import parse_user_id
from geekbaku.application.identity.use_cases.get_current_user import GetCurrentUser
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import InactiveUserError, UserNotFoundError
from geekbaku.domain.identity.value_objects import UserId
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import FakePasswordHasher


class TestGetCurrentUser:
    async def test_returns_fresh_user_data(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        registered = await RegisterUser(uow, FakePasswordHasher()).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        result = await GetCurrentUser(uow).execute(parse_user_id(registered.id))

        assert result.email == "ash@geekbaku.dev"

    async def test_raises_when_user_not_found(self) -> None:
        uow = InMemoryIdentityUnitOfWork()

        with pytest.raises(UserNotFoundError):
            await GetCurrentUser(uow).execute(UserId.new())

    async def test_raises_when_user_inactive(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        registered = await RegisterUser(uow, FakePasswordHasher()).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )
        user_id = parse_user_id(registered.id)
        user = await uow.users.get_by_id(user_id)
        assert user is not None
        user.deactivate()
        await uow.users.update(user)

        with pytest.raises(InactiveUserError):
            await GetCurrentUser(uow).execute(user_id)
