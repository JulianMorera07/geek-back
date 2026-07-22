from geekbaku.application.identity.mappers import build_identity, user_to_dto
from geekbaku.domain.identity.entities import Permission, Role, User
from geekbaku.domain.identity.value_objects import Email, PermissionId, RoleId, UserId, Username


def make_user() -> User:
    return User(id=UserId.new(), email=Email("ash@geekbaku.dev"), username=Username("ash"))


class TestUserToDto:
    def test_maps_roles_and_flattened_permission_keys(self) -> None:
        user = make_user()
        permission = Permission(id=PermissionId.new(), resource="catalog", action="read")
        role = Role(id=RoleId.new(), name="user", permission_ids={permission.id})

        dto = user_to_dto(user, roles=[role], permissions=[permission])

        assert dto.email == "ash@geekbaku.dev"
        assert dto.roles[0].name == "user"
        assert dto.permissions == ("catalog:read",)


class TestBuildIdentity:
    def test_derives_claims_from_roles_and_permissions(self) -> None:
        user = make_user()
        permission = Permission(id=PermissionId.new(), resource="catalog", action="read")
        role = Role(id=RoleId.new(), name="user", permission_ids={permission.id})

        identity = build_identity(user, [role], [permission])

        assert identity.user_id == user.id
        assert identity.roles == frozenset({"user"})
        assert identity.permissions == frozenset({"catalog:read"})
