"""Domain / application exception types.

Exceptions raised by the application layer carry a stable ``code`` string that
the API layer maps to RFC 7807 ``code`` fields and HTTP status codes (see
``app/api/errors.py``).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for every domain / application exception. The ``code`` attribute is
    machine-readable and stable across versions; messages are human-readable
    and MAY change."""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)


# ---------- Authentication ----------


class InvalidCredentialsError(DomainError):
    """Login failure — email unknown, password wrong, or user inactive. The
    public-facing message is intentionally identical for all three cases to
    avoid being an enumeration oracle. Internal logs distinguish the cases."""

    code = "INVALID_CREDENTIALS"
    http_status = 401


class UnauthenticatedError(DomainError):
    code = "UNAUTHENTICATED"
    http_status = 401


class AccessTokenExpiredError(DomainError):
    code = "ACCESS_TOKEN_EXPIRED"
    http_status = 401


class AccessTokenWrongTypeError(DomainError):
    code = "ACCESS_TOKEN_WRONG_TYPE"
    http_status = 401


class AccessTokenMalformedError(DomainError):
    code = "ACCESS_TOKEN_MALFORMED"
    http_status = 401


class RefreshTokenExpiredError(DomainError):
    code = "REFRESH_TOKEN_EXPIRED"
    http_status = 401


class RefreshTokenRevokedError(DomainError):
    code = "REFRESH_TOKEN_REVOKED"
    http_status = 401


class RefreshTokenMalformedError(DomainError):
    code = "REFRESH_TOKEN_MALFORMED"
    http_status = 401


# ---------- User account ----------


class EmailAlreadyRegisteredError(DomainError):
    code = "EMAIL_ALREADY_REGISTERED"
    http_status = 409


class PasswordTooShortError(DomainError):
    code = "PASSWORD_TOO_SHORT"
    http_status = 422


class PasswordTooLongError(DomainError):
    code = "PASSWORD_TOO_LONG"
    http_status = 422


# ---------- Password reset ----------


class ResetTokenExpiredError(DomainError):
    code = "RESET_TOKEN_EXPIRED"
    http_status = 400


class ResetTokenAlreadyUsedError(DomainError):
    code = "RESET_TOKEN_ALREADY_USED"
    http_status = 400


class ResetTokenInvalidError(DomainError):
    code = "RESET_TOKEN_INVALID"
    http_status = 400


# ---------- Authorisation ----------


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


# ---------- Components ----------


class ComponentNotFoundError(DomainError):
    code = "COMPONENT_NOT_FOUND"
    http_status = 404


class ComponentMpnAlreadyRegisteredError(DomainError):
    code = "MPN_ALREADY_REGISTERED"
    http_status = 409


# ---------- Modules ----------


class ModuleNotFoundError(DomainError):
    code = "MODULE_NOT_FOUND"
    http_status = 404


class ModuleSkuAlreadyRegisteredError(DomainError):
    code = "MODULE_SKU_ALREADY_REGISTERED"
    http_status = 409


class ModuleCycleDetectedError(DomainError):
    """Adding a child module would close a cycle in the module DAG."""

    code = "MODULE_CYCLE_DETECTED"
    http_status = 422


class ChildAlreadyPresentError(DomainError):
    """`(parent, child)` edge already exists — update `quantity` instead."""

    code = "CHILD_ALREADY_PRESENT"
    http_status = 422


class InvalidChildReferenceError(DomainError):
    """XOR violation on a child reference, or the referenced row is missing."""

    code = "INVALID_CHILD_REFERENCE"
    http_status = 422


# ---------- Misc ----------


class RateLimitExceededError(DomainError):
    code = "RATE_LIMIT_EXCEEDED"
    http_status = 429
