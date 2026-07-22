from geekbaku.infrastructure.identity.password_hasher import Argon2PasswordHasher


class TestArgon2PasswordHasher:
    def test_verify_succeeds_for_correct_password(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("Pikachu123")

        assert hasher.verify("Pikachu123", hashed) is True

    def test_verify_fails_for_wrong_password(self) -> None:
        hasher = Argon2PasswordHasher()
        hashed = hasher.hash("Pikachu123")

        assert hasher.verify("wrong-password", hashed) is False

    def test_verify_fails_for_malformed_hash(self) -> None:
        hasher = Argon2PasswordHasher()

        assert hasher.verify("Pikachu123", "not-a-real-hash") is False

    def test_hash_is_not_the_plaintext(self) -> None:
        hasher = Argon2PasswordHasher()

        assert hasher.hash("Pikachu123") != "Pikachu123"
