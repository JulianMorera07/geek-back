import pytest

from geekbaku.application.identity.dto import RegisterUserCommand
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import InvalidCredentialsError
from geekbaku.infrastructure.identity.providers.password_provider import (
    PasswordAuthenticationProvider,
)
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import FakePasswordHasher


class TestPasswordAuthenticationProvider:
    async def test_authenticates_with_correct_credentials(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        hasher = FakePasswordHasher()
        await RegisterUser(uow, hasher).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )
        provider = PasswordAuthenticationProvider(hasher)

        user = await provider.authenticate(
            {"email": "ash@geekbaku.dev", "password": "Pikachu123"}, uow
        )

        assert str(user.email) == "ash@geekbaku.dev"

    async def test_rejects_unknown_email_without_leaking_existence(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        provider = PasswordAuthenticationProvider(FakePasswordHasher())

        with pytest.raises(InvalidCredentialsError):
            await provider.authenticate(
                {"email": "nobody@geekbaku.dev", "password": "whatever"}, uow
            )

    async def test_rejects_wrong_password(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        hasher = FakePasswordHasher()
        await RegisterUser(uow, hasher).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )
        provider = PasswordAuthenticationProvider(hasher)

        with pytest.raises(InvalidCredentialsError):
            await provider.authenticate({"email": "ash@geekbaku.dev", "password": "wrong"}, uow)

    async def test_rejects_malformed_email(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        provider = PasswordAuthenticationProvider(FakePasswordHasher())

        with pytest.raises(InvalidCredentialsError):
            await provider.authenticate({"email": "not-an-email", "password": "x"}, uow)
