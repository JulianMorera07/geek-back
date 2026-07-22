import pytest

from geekbaku.application.identity.dto import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
    RegisterUserCommand,
)
from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.application.identity.use_cases.login_user import LoginUser
from geekbaku.application.identity.use_cases.logout_user import LogoutUser
from geekbaku.application.identity.use_cases.refresh_access_token import RefreshAccessToken
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import RefreshTokenNotFoundError, RefreshTokenRevokedError
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


class TestLogoutUser:
    async def test_logout_revokes_session_and_refresh_token(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        await RegisterUser(uow, FakePasswordHasher()).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )
        registry = AuthenticationProviderRegistry()
        registry.register(PasswordAuthenticationProvider(FakePasswordHasher()))
        tokens = FakeTokenService()
        login_result = await LoginUser(uow, registry, tokens, FakeBruteForceGuard()).execute(
            LoginCommand(email="ash@geekbaku.dev", password="Pikachu123")
        )

        await LogoutUser(uow, tokens).execute(
            LogoutCommand(refresh_token=login_result.refresh_token)
        )

        with pytest.raises(RefreshTokenRevokedError):
            await RefreshAccessToken(uow, tokens).execute(
                RefreshTokenCommand(refresh_token=login_result.refresh_token)
            )

    async def test_logout_with_unknown_token_raises(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        tokens = FakeTokenService()

        with pytest.raises(RefreshTokenNotFoundError):
            await LogoutUser(uow, tokens).execute(LogoutCommand(refresh_token="never-issued"))
