import pytest

from geekbaku.application.identity.dto import RegisterUserCommand
from geekbaku.application.identity.mappers import parse_user_id
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import UserAlreadyExistsError, WeakPasswordError
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import FakePasswordHasher


class TestRegisterUser:
    async def test_registers_user_with_default_role(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        use_case = RegisterUser(uow, FakePasswordHasher())

        result = await use_case.execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        assert result.email == "ash@geekbaku.dev"
        assert result.username == "ash"
        assert [r.name for r in result.roles] == ["user"]
        assert "catalog:read" in result.permissions

    async def test_creates_password_credential(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        use_case = RegisterUser(uow, FakePasswordHasher())

        result = await use_case.execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        stored_user = await uow.users.get_by_id(parse_user_id(result.id))
        assert stored_user is not None
        credential = await uow.credentials.get_by_user_and_provider(stored_user.id, "password")
        assert credential is not None
        assert credential.secret_hash == "hashed:Pikachu123"

    async def test_rejects_duplicate_email(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        use_case = RegisterUser(uow, FakePasswordHasher())
        command = RegisterUserCommand(
            email="ash@geekbaku.dev", username="ash", password="Pikachu123"
        )
        await use_case.execute(command)

        with pytest.raises(UserAlreadyExistsError):
            await use_case.execute(
                RegisterUserCommand(
                    email="ash@geekbaku.dev", username="other", password="Pikachu123"
                )
            )

    async def test_rejects_duplicate_username(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        use_case = RegisterUser(uow, FakePasswordHasher())
        await use_case.execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        with pytest.raises(UserAlreadyExistsError):
            await use_case.execute(
                RegisterUserCommand(
                    email="other@geekbaku.dev", username="ash", password="Pikachu123"
                )
            )

    async def test_rejects_weak_password(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        use_case = RegisterUser(uow, FakePasswordHasher())

        with pytest.raises(WeakPasswordError):
            await use_case.execute(
                RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="weak")
            )
