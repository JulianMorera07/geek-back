import pytest

from geekbaku.application.identity.dto import LoginCommand, RefreshTokenCommand, RegisterUserCommand
from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.application.identity.use_cases.login_user import LoginUser
from geekbaku.application.identity.use_cases.refresh_access_token import RefreshAccessToken
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.domain.identity.exceptions import (
    AuthenticationError,
    RefreshTokenNotFoundError,
    RefreshTokenReusedError,
)
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


async def _login() -> tuple[InMemoryIdentityUnitOfWork, FakeTokenService, str]:
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
    return uow, tokens, login_result.refresh_token


class TestRefreshAccessToken:
    async def test_refresh_rotates_token(self) -> None:
        uow, tokens, refresh_token = await _login()
        use_case = RefreshAccessToken(uow, tokens)

        result = await use_case.execute(RefreshTokenCommand(refresh_token=refresh_token))

        assert result.refresh_token != refresh_token
        assert result.access_token.value

    async def test_reusing_rotated_token_raises_and_revokes_session(self) -> None:
        uow, tokens, refresh_token = await _login()
        use_case = RefreshAccessToken(uow, tokens)
        await use_case.execute(RefreshTokenCommand(refresh_token=refresh_token))

        with pytest.raises(RefreshTokenReusedError):
            await use_case.execute(RefreshTokenCommand(refresh_token=refresh_token))

    async def test_new_token_also_revoked_after_reuse_detected(self) -> None:
        uow, tokens, refresh_token = await _login()
        use_case = RefreshAccessToken(uow, tokens)
        first_rotation = await use_case.execute(RefreshTokenCommand(refresh_token=refresh_token))

        with pytest.raises(RefreshTokenReusedError):
            await use_case.execute(RefreshTokenCommand(refresh_token=refresh_token))

        # La sesión completa quedó revocada: el token nuevo también falla,
        # aunque nunca se haya usado.
        with pytest.raises(AuthenticationError):
            await use_case.execute(RefreshTokenCommand(refresh_token=first_rotation.refresh_token))

    async def test_unknown_token_raises_not_found(self) -> None:
        uow, tokens, _refresh_token = await _login()
        use_case = RefreshAccessToken(uow, tokens)

        with pytest.raises(RefreshTokenNotFoundError):
            await use_case.execute(RefreshTokenCommand(refresh_token="never-issued"))
