from __future__ import annotations


class SamsungHealthError(Exception):
    """Base exception for all Samsung Health Cloud errors."""


# Backward-compatible alias
SamsungHealthCloudError = SamsungHealthError


class AuthenticationError(SamsungHealthError):
    """Raised when authentication fails, credentials are missing, or tokens are expired."""


class NetworkError(SamsungHealthError):
    """Raised when remote communication with Samsung Cloud endpoints fails."""


class StateError(SamsungHealthError):
    """Raised when local filesystem state, cache, or lock files are corrupted or invalid."""


class UsageError(SamsungHealthError):
    """Raised when invalid parameters, arguments, or ranges are provided."""


class DataError(SamsungHealthError):
    """Raised when health records or responses cannot be parsed or validated."""


class SchemaError(SamsungHealthError):
    """Raised when schema validation or manifest resolution fails."""


class RateLimitError(SamsungHealthError):
    """Raised when Samsung Cloud rate limits or throttling are encountered."""
