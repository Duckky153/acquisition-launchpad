class DomainError(Exception):
    """Base exception for expected, client-correctable failures."""


class ConflictError(DomainError):
    """The request conflicts with current persistent state."""


class NotFoundError(DomainError):
    """The requested resource does not exist."""


class ValidationError(DomainError):
    """Cross-record domain validation failed."""
