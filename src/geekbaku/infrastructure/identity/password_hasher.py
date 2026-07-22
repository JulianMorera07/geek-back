"""Password Hashing: implementación concreta de
`application.identity.ports.PasswordHasher` con Argon2id
(`argon2-cffi`, ya declarado en `pyproject.toml` — algoritmo recomendado
por OWASP sobre bcrypt/PBKDF2 para hashing de contraseñas nuevas).
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = _Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self._hasher.verify(hashed, password)
        except (VerificationError, InvalidHash):
            return False


__all__ = ["Argon2PasswordHasher"]
