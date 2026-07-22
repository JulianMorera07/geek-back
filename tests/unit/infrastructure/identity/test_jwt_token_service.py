import time

import pytest

from geekbaku.domain.identity.exceptions import AuthenticationError
from geekbaku.domain.identity.value_objects import Identity, UserId
from geekbaku.infrastructure.identity.jwt_token_service import JwtTokenService


def make_identity() -> Identity:
    return Identity(
        user_id=UserId.new(),
        email="ash@geekbaku.dev",
        roles=frozenset({"user"}),
        permissions=frozenset({"catalog:read"}),
    )


class TestJwtTokenService:
    def test_issue_and_decode_roundtrip(self) -> None:
        service = JwtTokenService(secret_key="test-secret-with-at-least-32-bytes!!")
        identity = make_identity()

        token, expires_in = service.issue_access_token(identity)
        decoded = service.decode_access_token(token)

        assert expires_in == 900
        assert decoded.user_id == identity.user_id
        assert decoded.email == identity.email
        assert decoded.roles == identity.roles
        assert decoded.permissions == identity.permissions

    def test_decode_expired_token_raises_authentication_error(self) -> None:
        service = JwtTokenService(
            secret_key="test-secret-with-at-least-32-bytes!!", access_token_ttl_seconds=1
        )
        token, _ = service.issue_access_token(make_identity())
        time.sleep(1.5)

        with pytest.raises(AuthenticationError):
            service.decode_access_token(token)

    def test_decode_tampered_token_raises_authentication_error(self) -> None:
        service = JwtTokenService(secret_key="test-secret-with-at-least-32-bytes!!")
        token, _ = service.issue_access_token(make_identity())

        with pytest.raises(AuthenticationError):
            service.decode_access_token(token + "tampered")

    def test_decode_token_signed_with_different_secret_raises(self) -> None:
        issuer = JwtTokenService(secret_key="secret-a-with-at-least-32-bytes!!!!")
        verifier = JwtTokenService(secret_key="secret-b-with-at-least-32-bytes!!!!")
        token, _ = issuer.issue_access_token(make_identity())

        with pytest.raises(AuthenticationError):
            verifier.decode_access_token(token)

    def test_refresh_token_value_is_opaque_and_hash_is_deterministic(self) -> None:
        service = JwtTokenService(secret_key="test-secret-with-at-least-32-bytes!!")

        raw = service.generate_refresh_token_value()

        assert service.hash_refresh_token(raw) == service.hash_refresh_token(raw)
        assert service.hash_refresh_token(raw) != raw

    def test_refresh_token_ttl_seconds_configurable(self) -> None:
        service = JwtTokenService(
            secret_key="test-secret-with-at-least-32-bytes!!", refresh_token_ttl_seconds=123
        )
        assert service.refresh_token_ttl_seconds() == 123
