"""Password and token hashing primitives.

- ``hash_password`` / ``verify_password``: Argon2id for user passwords.
- ``argon2_hash`` / ``argon2_verify``: Argon2id for password-reset tokens
  (lower-entropy strings travelling by email).
- ``sha256_hex``: SHA-256 hex digest for refresh-token ``jti`` lookup. The
  ``jti`` is already 128-bit CSPRNG output, so SHA-256 is sufficient.

The Argon2 parameters are the passlib defaults for the ``argon2`` scheme,
explicitly pinned here so cost changes are an intentional and reviewed event.
"""

from __future__ import annotations

import hashlib

from passlib.context import CryptContext

_password_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=3,
    argon2__memory_cost=64 * 1024,
    argon2__parallelism=4,
    argon2__hash_len=32,
)

_token_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=2,
    argon2__memory_cost=32 * 1024,
    argon2__parallelism=2,
    argon2__hash_len=32,
)


def hash_password(plaintext: str) -> str:
    return _password_context.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return _password_context.verify(plaintext, hashed)
    except Exception:
        return False


def argon2_hash(value: str) -> str:
    return _token_context.hash(value)


def argon2_verify(value: str, hashed: str) -> bool:
    try:
        return _token_context.verify(value, hashed)
    except Exception:
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
