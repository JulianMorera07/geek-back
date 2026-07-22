import pytest

from geekbaku.application.identity.registry import AuthenticationProviderRegistry
from geekbaku.domain.identity.exceptions import (
    AuthenticationProviderAlreadyRegisteredError,
    AuthenticationProviderNotFoundError,
)


class _StubProvider:
    provider_id = "stub"

    async def authenticate(self, credentials: object, uow: object) -> object:
        raise NotImplementedError


class TestAuthenticationProviderRegistry:
    def test_register_and_get(self) -> None:
        registry = AuthenticationProviderRegistry()
        provider = _StubProvider()

        registry.register(provider)

        assert registry.get("stub") is provider
        assert "stub" in registry
        assert registry.list_provider_ids() == ("stub",)

    def test_register_twice_raises(self) -> None:
        registry = AuthenticationProviderRegistry()
        registry.register(_StubProvider())

        with pytest.raises(AuthenticationProviderAlreadyRegisteredError):
            registry.register(_StubProvider())

    def test_get_unknown_raises(self) -> None:
        registry = AuthenticationProviderRegistry()

        with pytest.raises(AuthenticationProviderNotFoundError):
            registry.get("unknown")
