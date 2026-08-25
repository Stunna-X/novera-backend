"""Password hashing and verification utilities."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.exceptions import VerifyMismatchError


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return password_hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    try:
        return password_hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
