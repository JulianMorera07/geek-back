from datetime import UTC, datetime, timedelta

import pytest

from geekbaku.domain.identity.entities import Permission, RefreshToken, Role, Session, User
from geekbaku.domain.identity.exceptions import RefreshTokenReusedError
from geekbaku.domain.identity.value_objects import (
    Email,
    PermissionId,
    Profile,
    RefreshTokenId,
    RoleId,
    SessionId,
    UserId,
    Username,
    UserSettings,
)


def make_user() -> User:
    return User(id=UserId.new(), email=Email("ash@geekbaku.dev"), username=Username("ash"))


class TestPermission:
    def test_key_combines_resource_and_action(self) -> None:
        permission = Permission(id=PermissionId.new(), resource="anime", action="read")
        assert permission.key == "anime:read"


class TestRole:
    def test_grant_and_revoke_permission(self) -> None:
        role = Role(id=RoleId.new(), name="user")
        permission_id = PermissionId.new()

        role.grant(permission_id)
        assert permission_id in role.permission_ids

        role.revoke(permission_id)
        assert permission_id not in role.permission_ids


class TestUser:
    def test_assign_and_revoke_role(self) -> None:
        user = make_user()
        role_id = RoleId.new()

        user.assign_role(role_id)
        assert role_id in user.role_ids

        user.revoke_role(role_id)
        assert role_id not in user.role_ids

    def test_update_profile_replaces_it_whole(self) -> None:
        user = make_user()
        user.update_profile(Profile(display_name="Ash", bio="Trainer"))
        assert user.profile.display_name == "Ash"
        assert user.profile.bio == "Trainer"

    def test_update_settings_replaces_it_whole(self) -> None:
        user = make_user()
        user.update_settings(UserSettings(theme="dark"))
        assert user.settings.theme == "dark"

    def test_deactivate_and_activate(self) -> None:
        user = make_user()
        user.deactivate()
        assert user.is_active is False
        user.activate()
        assert user.is_active is True


class TestSession:
    def test_is_active_false_when_expired(self) -> None:
        now = datetime.now(UTC)
        session = Session(
            id=SessionId.new(), user_id=UserId.new(), expires_at=now - timedelta(seconds=1)
        )
        assert session.is_expired(now=now) is True
        assert session.is_active(now=now) is False

    def test_is_active_false_when_revoked(self) -> None:
        now = datetime.now(UTC)
        session = Session(
            id=SessionId.new(), user_id=UserId.new(), expires_at=now + timedelta(hours=1)
        )
        session.revoke(now=now)
        assert session.is_active(now=now) is False


class TestRefreshToken:
    def make_token(self, *, expires_delta: timedelta = timedelta(hours=1)) -> RefreshToken:
        now = datetime.now(UTC)
        return RefreshToken(
            id=RefreshTokenId.new(),
            user_id=UserId.new(),
            session_id=SessionId.new(),
            token_hash="hash",
            expires_at=now + expires_delta,
        )

    def test_is_usable_when_fresh(self) -> None:
        token = self.make_token()
        assert token.is_usable() is True

    def test_is_not_usable_when_expired(self) -> None:
        token = self.make_token(expires_delta=timedelta(seconds=-1))
        assert token.is_usable() is False

    def test_rotate_marks_token_as_rotated(self) -> None:
        token = self.make_token()
        new_id = RefreshTokenId.new()

        token.rotate(new_id)

        assert token.rotated_to == new_id
        assert token.is_usable() is False

    def test_rotate_twice_raises_reuse_error(self) -> None:
        token = self.make_token()
        token.rotate(RefreshTokenId.new())

        with pytest.raises(RefreshTokenReusedError):
            token.rotate(RefreshTokenId.new())

    def test_rotate_revoked_token_raises_reuse_error(self) -> None:
        token = self.make_token()
        token.revoke()

        with pytest.raises(RefreshTokenReusedError):
            token.rotate(RefreshTokenId.new())
