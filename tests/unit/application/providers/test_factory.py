import pytest

from geekbaku.application.providers.factory import ProviderFactory
from geekbaku.domain.providers.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
)
from geekbaku.domain.providers.value_objects import ProviderConfiguration, ProviderId
from tests.unit.application.providers.fakes import FakeProviderPort

CONFIGURATION = ProviderConfiguration(
    provider_id=ProviderId("provider-a"), base_url="https://example.com"
)


class TestProviderFactory:
    def test_starts_empty(self) -> None:
        factory = ProviderFactory()
        assert factory.list_kinds() == ()

    def test_register_and_create(self) -> None:
        factory = ProviderFactory()
        created = FakeProviderPort()
        factory.register_constructor("provider_a", lambda config: created)

        instance = factory.create("provider_a", CONFIGURATION)

        assert instance is created

    def test_constructor_receives_configuration(self) -> None:
        factory = ProviderFactory()
        received: list[ProviderConfiguration] = []

        def constructor(config: ProviderConfiguration) -> FakeProviderPort:
            received.append(config)
            return FakeProviderPort()

        factory.register_constructor("provider_a", constructor)
        factory.create("provider_a", CONFIGURATION)

        assert received == [CONFIGURATION]

    def test_register_duplicate_kind_raises(self) -> None:
        factory = ProviderFactory()
        factory.register_constructor("provider_a", lambda config: FakeProviderPort())

        with pytest.raises(ProviderAlreadyRegisteredError):
            factory.register_constructor("provider_a", lambda config: FakeProviderPort())

    def test_create_unknown_kind_raises(self) -> None:
        factory = ProviderFactory()
        with pytest.raises(ProviderNotFoundError):
            factory.create("unknown", CONFIGURATION)

    def test_unregister_constructor(self) -> None:
        factory = ProviderFactory()
        factory.register_constructor("provider_a", lambda config: FakeProviderPort())

        factory.unregister_constructor("provider_a")

        assert factory.list_kinds() == ()

    def test_unregister_unknown_kind_raises(self) -> None:
        factory = ProviderFactory()
        with pytest.raises(ProviderNotFoundError):
            factory.unregister_constructor("unknown")
