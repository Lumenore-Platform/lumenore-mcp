# Copyright © Lumenore Inc. All rights reserved.

"""
Request context storage for sharing HTTP headers between middleware and tools.

The middleware stores the current request's headers in a ContextVar and the
tools read them back. A ContextVar is scoped to the current asyncio task, so
concurrent requests never see each other's credentials. There is deliberately
no thread-local fallback: thread-local state is shared between concurrent
asyncio requests on the same thread and could leak one user's credentials to
another user's request.
"""

from contextvars import ContextVar
from typing import Dict, Optional

_request_headers_var: ContextVar[Optional[Dict[str, str]]] = ContextVar(
    "request_headers", default=None
)


def set_request_headers(headers: Dict[str, str]) -> None:
    """Store request headers for the current request context."""
    _request_headers_var.set(dict(headers or {}))


def get_request_headers() -> Dict[str, str]:
    """Return the current request's headers, or an empty dict if not set."""
    return _request_headers_var.get() or {}


def clear_request_headers() -> None:
    """Clear request headers after the request is processed."""
    _request_headers_var.set(None)


def is_bearer(value) -> bool:
    """True only for a well-formed ``Bearer <token>`` Authorization value."""
    if not isinstance(value, str):
        return False
    scheme, _, token = value.strip().partition(" ")
    return scheme.lower() == "bearer" and bool(token.strip())


def client_credentials(headers: Optional[Dict[str, str]]):
    """Return (client_id, client_secret) from lower-cased request headers."""
    headers = headers or {}
    client_id = headers.get("lumenore-client-id") or headers.get("x-lumenore-client-id")
    client_secret = headers.get("lumenore-client-secret") or headers.get(
        "x-lumenore-client-secret"
    )
    return (client_id or None, client_secret or None)
