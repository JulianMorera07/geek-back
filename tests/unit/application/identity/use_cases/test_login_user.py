import pytest

from geekbaku.application.identity.dto import LoginCommand, RegisterUserCommand
from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.application.identity.use_cases.login_user import LoginUser
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import InvalidCredentialsError, TooManyAttemptsError
from geekbaku.infrastructure.identity.providers.password_provider import (
    PasswordAuthenticationProvider,
)
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import (
    FakeBruteForceGuard,
    FakePasswordHasher,
    FakeTokenService,
)


async def _uow_with_registered_user() -> InMemoryIdentityUnitOfWork:
    uow = InMemoryIdentityUnitOfWork()
    await RegisterUser(uow, FakePasswordHasher()).execute(
        RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
    )
    return uow


def _registry() -> AuthenticationProviderRegistry:
    registry = AuthenticationProviderRegistry()
    registry.register(PasswordAuthenticationProvider(FakePasswordHasher()))
    return registry


class TestLoginUser:
    async def test_login_returns_tokens_and_user(self) -> None:
        uow = await _uow_with_registered_user()
        use_case = LoginUser(uow, _registry(), FakeTokenService(), FakeBruteForceGuard())

        result = await use_case.execute(
            LoginCommand(email="ash@geekbaku.dev", password="Pikachu123")
        )

        assert result.access_token.value
        assert result.refresh_token
        assert result.user.email == "ash@geekbaku.dev"

    async def test_login_creates_session_and_refresh_token(self) -> None:
        uow = await _uow_with_registered_user()
        use_case = LoginUser(uow, _registry(), FakeTokenService(), FakeBruteForceGuard())

        await use_case.execute(LoginCommand(email="ash@geekbaku.dev", password="Pikachu123"))

        user = await uow.users.get_by_email("ash@geekbaku.dev")
        assert user is not None

    async def test_wrong_password_raises_and_registers_failure(self) -> None:
        uow = await _uow_with_registered_user()
        guard = FakeBruteForceGuard()
        use_case = LoginUser(uow, _registry(), FakeTokenService(), guard)

        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(LoginCommand(email="ash@geekbaku.dev", password="wrong"))

        assert guard.failures

    async def test_blocked_key_raises_too_many_attempts(self) -> None:
        uow = await _uow_with_registered_user()
        guard = FakeBruteForceGuard(blocked_keys={"ash@geekbaku.dev:unknown"})
        use_case = LoginUser(uow, _registry(), FakeTokenService(), guard)

        with pytest.raises(TooManyAttemptsError):
            await use_case.execute(LoginCommand(email="ash@geekbaku.dev", password="Pikachu123"))
