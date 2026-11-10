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
