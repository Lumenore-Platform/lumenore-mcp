class AuthorizationError(RuntimeError):
    """Raised when no valid authorization token is found."""


class APIRequestError(RuntimeError):
    """Raised when an API request fails due to a network or HTTP issue."""


class UnexpectedAPIError(RuntimeError):
    """Raised when an unexpected error occurs during API handling."""

class APIRequestTimeout(RuntimeError):
    """Raised when the outbound API request times out."""

class AuthenticationError(Exception):
    """Raised when authentication fails"""

class APIError(Exception):
    """Raised when API calls fail"""
