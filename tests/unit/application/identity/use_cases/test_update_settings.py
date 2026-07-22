from geekbaku.application.identity.dto import RegisterUserCommand, UpdateSettingsCommand
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.application.identity.use_cases.update_settings import UpdateSettings
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import FakePasswordHasher


class TestUpdateSettings:
    async def test_updates_only_given_fields(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        registered = await RegisterUser(uow, FakePasswordHasher()).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        first = await UpdateSettings(uow).execute(
            UpdateSettingsCommand(user_id=registered.id, theme="dark")
        )
        assert first.settings.theme == "dark"
        assert first.settings.language == "es"

        second = await UpdateSettings(uow).execute(
            UpdateSettingsCommand(user_id=registered.id, notifications_enabled=False)
        )

        assert second.settings.theme == "dark"
        assert second.settings.notifications_enabled is False
