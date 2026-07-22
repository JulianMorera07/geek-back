import pytest

from geekbaku.domain.identity.exceptions import (
    InactiveUserError,
    PermissionDeniedError,
    WeakPasswordError,
)
from geekbaku.domain.identity.services import AuthorizationService, PasswordPolicy
from geekbaku.domain.identity.value_objects import Identity, UserId


def make_identity(*, is_active: bool = True, permissions: frozenset[str] = frozenset()) -> Identity:
    return Identity(
        user_id=UserId.new(),
        email="ash@geekbaku.dev",
        roles=frozenset({"user"}),
        permissions=permissions,
        is_active=is_active,
    )


class TestPasswordPolicy:
    def test_accepts_strong_password(self) -> None:
        PasswordPolicy.validate("Pikachu123")

    @pytest.mark.parametrize(
        "password",
        ["short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere"],
    )
    def test_rejects_weak_password(self, password: str) -> None:
        with pytest.raises(WeakPasswordError):
            PasswordPolicy.validate(password)


class TestAuthorizationService:
    def test_authorize_passes_when_permission_present(self) -> None:
        identity = make_identity(permissions=frozenset({"catalog:read"}))
        AuthorizationService.authorize(identity, "catalog", "read")

    def test_authorize_raises_when_permission_missing(self) -> None:
        identity = make_identity(permissions=frozenset())
        with pytest.raises(PermissionDeniedError):
            AuthorizationService.authorize(identity, "catalog", "read")

    def test_authorize_raises_when_inactive(self) -> None:
        identity = make_identity(is_active=False, permissions=frozenset({"catalog:read"}))
        with pytest.raises(InactiveUserError):
            AuthorizationService.authorize(identity, "catalog", "read")

    def test_authorize_evaluates_extra_policies(self) -> None:
        identity = make_identity(permissions=frozenset({"catalog:read"}))

        with pytest.raises(PermissionDeniedError):
            AuthorizationService.authorize(
                identity, "catalog", "read", policies=[lambda _identity: False]
            )
