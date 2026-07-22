import pytest

from geekbaku.application.providers.registry import ProviderRegistry
from geekbaku.domain.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
)
from geekbaku.domain.providers.value_objects import ProviderId
from tests.unit.application.providers.fakes import FakeProviderPort

PROVIDER_A = ProviderId("provider-a")
PROVIDER_B = ProviderId("provider-b")
PROVIDER_C = ProviderId("provider-c")


class TestRegistration:
    def test_register_and_get(self) -> None:
        registry = ProviderRegistry()
        adapter = FakeProviderPort()

        registry.register(PROVIDER_A, adapter)

        registration = registry.get(PROVIDER_A)
        assert registration.adapter is adapter
        assert registration.provider.id == PROVIDER_A
        assert registration.provider.is_enabled is True
        assert registration.provider.priority == 0

    def test_register_duplicate_raises(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort())

        with pytest.raises(ProviderAlreadyRegisteredError):
            registry.register(PROVIDER_A, FakeProviderPort())

    def test_get_unknown_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get(PROVIDER_A)

    def test_get_adapter_unknown_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get_adapter(PROVIDER_A)

    def test_unregister_removes_registration(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort())

        registry.unregister(PROVIDER_A)

        assert registry.list_provider_ids() == ()

    def test_unregister_unknown_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.unregister(PROVIDER_A)


class TestEnableDisable:
    def test_disable_and_enable(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort())

        registry.disable(PROVIDER_A)
        assert registry.get(PROVIDER_A).provider.is_enabled is False
        assert registry.list_enabled() == ()

        registry.enable(PROVIDER_A)
        assert registry.get(PROVIDER_A).provider.is_enabled is True
        assert len(registry.list_enabled()) == 1

    def test_register_disabled_directly(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort(), is_enabled=False)

        assert registry.list_enabled() == ()
        assert len(registry.list_all()) == 1


class TestPriorityOrdering:
    def test_orders_enabled_providers_by_priority_descending(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort(), priority=5)
        registry.register(PROVIDER_B, FakeProviderPort(), priority=10)
        registry.register(PROVIDER_C, FakeProviderPort(), priority=1)

        ordered = registry.list_enabled_by_priority()

        assert [r.provider.id for r in ordered] == [PROVIDER_B, PROVIDER_A, PROVIDER_C]

    def test_excludes_disabled_providers(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort(), priority=10)
        registry.register(PROVIDER_B, FakeProviderPort(), priority=5, is_enabled=False)

        ordered = registry.list_enabled_by_priority()

        assert [r.provider.id for r in ordered] == [PROVIDER_A]

    def test_stable_order_on_ties(self) -> None:
        registry = ProviderRegistry()
        registry.register(PROVIDER_A, FakeProviderPort(), priority=1)
        registry.register(PROVIDER_B, FakeProviderPort(), priority=1)

        ordered = registry.list_enabled_by_priority()

        assert [r.provider.id for r in ordered] == [PROVIDER_A, PROVIDER_B]
