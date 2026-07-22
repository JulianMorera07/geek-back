from geekbaku.domain.identity.entities import Credential, User
from geekbaku.domain.identity.value_objects import CredentialId, Email, UserId, Username
from geekbaku.infrastructure.identity.repositories.in_memory_identity_repository import (
    InMemoryIdentityUnitOfWork,
)


class TestInMemoryIdentityUnitOfWork:
    async def test_seeds_default_roles(self) -> None:
        uow = InMemoryIdentityUnitOfWork()

        user_role = await uow.roles.get_by_name("user")
        admin_role = await uow.roles.get_by_name("admin")

        assert user_role is not None
        assert admin_role is not None
        assert user_role.is_system is True
        assert len(admin_role.permission_ids) > len(user_role.permission_ids)

    async def test_get_by_email_is_case_insensitive_on_normalized_value(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        user = User(id=UserId.new(), email=Email("Ash@GeekBaku.dev"), username=Username("ash"))
        await uow.users.add(user)

        found = await uow.users.get_by_email("ash@geekbaku.dev")

        assert found is user

    async def test_credentials_lookup_by_user_and_provider(self) -> None:
        uow = InMemoryIdentityUnitOfWork()
        user = User(id=UserId.new(), email=Email("ash@geekbaku.dev"), username=Username("ash"))
        await uow.users.add(user)
        credential = Credential(
            id=CredentialId.new(), user_id=user.id, provider_id="password", secret_hash="hash"
        )
        await uow.credentials.add(credential)

        found = await uow.credentials.get_by_user_and_provider(user.id, "password")

        assert found is credential
        assert await uow.credentials.get_by_user_and_provider(user.id, "google") is None
