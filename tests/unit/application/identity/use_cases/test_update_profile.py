from geekbaku.application.identity.dto import RegisterUserCommand, UpdateProfileCommand
from geekbaku.application.identity.use_cases.register_user import RegisterUser
from geekbaku.application.identity.use_cases.update_profile import UpdateProfile
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)
from tests.unit.application.identity.fakes import FakePasswordHasher


class TestUpdateProfile:
    async def test_updates_only_given_fields(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        registered = await RegisterUser(uow, FakePasswordHasher()).execute(
            RegisterUserCommand(email="ash@geekbaku.dev", username="ash", password="Pikachu123")
        )

        first = await UpdateProfile(uow).execute(
            UpdateProfileCommand(user_id=registered.id, display_name="Ash", bio="Trainer")
        )
        assert first.profile.display_name == "Ash"
        assert first.profile.bio == "Trainer"

        second = await UpdateProfile(uow).execute(
            UpdateProfileCommand(user_id=registered.id, avatar_url="https://cdn.example.com/a.png")
        )

        assert second.profile.display_name == "Ash"
        assert second.profile.bio == "Trainer"
        assert second.profile.avatar_url == "https://cdn.example.com/a.png"
