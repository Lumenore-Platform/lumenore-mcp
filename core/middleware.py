from config import config
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ValidationError
from core.request_context import (
    set_request_headers,
    clear_request_headers,
    is_bearer,
    client_credentials,
)
from utils.logger import get_logger

logger = get_logger()


class RawMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Validate and process authorization for tool calls.

        Supports multi-user authentication where users provide their own credentials
        via request headers. Falls back to server-level credentials if configured.

        Supported headers:
        - Authorization: Bearer token
        - Lumenore-Client-Id + Lumenore-Client-Secret (or the X- prefixed
          variants): OAuth2.0 client credentials
        """

        req_ctx = None
        headers = {}

        request = None

        if (
            hasattr(context, "fastmcp_context")
            and context.fastmcp_context is not None
            and hasattr(context.fastmcp_context, "request_context")
        ):
            req_ctx = context.fastmcp_context.request_context
            if (
                req_ctx is not None
                and hasattr(req_ctx, "request")
                and hasattr(req_ctx.request, "headers")
            ):
                request = req_ctx.request
                headers = {
                    k.lower(): v for k, v in dict(req_ctx.request.headers).items()
                }

        # Log request metadata only; never log header values or credentials.
        logger.debug(
            "[Middleware] Tool call: method=%s path=%s",
            getattr(request, "method", None),
            getattr(getattr(request, "url", None), "path", None),
        )

        # Store headers in shared context for tools to access
        set_request_headers(headers)

        # Check for credentials in request headers. Accept both the plain and
        # the X- prefixed client-credential header names.
        auth_header = (headers.get("authorization") or "").strip()
        client_id, client_secret = client_credentials(headers)

        # An Authorization header must be a Bearer token. Anything else is
        # rejected outright so it can never fall through to server-level
        # credentials.
        if auth_header and not is_bearer(auth_header):
            clear_request_headers()
            raise ValidationError(
                "401 Unauthorized: the Authorization header must be a Bearer token."
            )

        # Determine if we have valid credentials from any source
        has_header_token = bool(auth_header)
        has_header_client_creds = bool(client_id and client_secret)
        has_config_credentials = config.has_credentials()

        if not has_header_token and not has_header_client_creds and not has_config_credentials:
            clear_request_headers()
            raise ValidationError(
                "401 Unauthorized: No credentials provided. "
                "Please provide Authorization header with Bearer token, "
                "or Lumenore-Client-Id and Lumenore-Client-Secret headers "
                "(the X-Lumenore-Client-Id/X-Lumenore-Client-Secret variants "
                "are also accepted)."
            )

        logger.debug(
            "[Middleware] Auth source: %s",
            "authorization_header" if has_header_token
            else "client_credential_headers" if has_header_client_creds
            else "server_config",
        )

        try:
            return await call_next(context)
        finally:
            clear_request_headers()
