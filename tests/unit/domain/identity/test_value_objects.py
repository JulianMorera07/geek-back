import pytest

from geekbaku.domain.identity.value_objects import (
    Email,
    Identity,
    Profile,
    UserId,
    Username,
    UserSettings,
)
from geekbaku.domain.shared.errors import ValidationError


class TestEmail:
    def test_normalizes_case(self) -> None:
        assert str(Email("Ash@Geekbaku.DEV")) == "ash@geekbaku.dev"

    def test_rejects_invalid_format(self) -> None:
        with pytest.raises(ValidationError):
            Email("not-an-email")


class TestUsername:
    def test_accepts_valid_username(self) -> None:
        assert str(Username("ash_ketchum")) == "ash_ketchum"

    @pytest.mark.parametrize("value", ["ab", "a" * 33, "invalid username"])
    def test_rejects_invalid_username(self, value: str) -> None:
        with pytest.raises(ValidationError):
            Username(value)


class TestProfile:
    def test_rejects_bio_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Profile(bio="x" * 501)


class TestUserSettings:
    def test_rejects_invalid_theme(self) -> None:
        with pytest.raises(ValidationError):
            UserSettings(theme="rainbow")


class TestIdentity:
    def test_has_role_and_permission(self) -> None:
        identity = Identity(
            user_id=UserId.new(),
            email="ash@geekbaku.dev",
            roles=frozenset({"user"}),
            permissions=frozenset({"catalog:read"}),
        )

        assert identity.has_role("user")
        assert not identity.has_role("admin")
        assert identity.has_permission("catalog", "read")
        assert not identity.has_permission("catalog", "write")
