from config import config
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger()


class RawMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Ensure authorization token is present in request headers."""

        req_ctx = None
        headers = None

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

                headers = {
                    k.lower(): v for k, v in dict(req_ctx.request.headers).items()
                }

        auth_header = headers.get("authorization") if headers else None

        if not auth_header:

            if not config.TOKEN and not config.CLIENT_ID:
                raise ValidationError(
                    "401 Unauthorized: No authorization token provided"
                )

            if (
                req_ctx
                and hasattr(req_ctx, "request")
                and hasattr(req_ctx.request, "headers")
            ):
                req_ctx.request.headers.__setattr__("Authorization", config.TOKEN)

        else:

            if (
                req_ctx
                and hasattr(req_ctx, "request")
                and hasattr(req_ctx.request, "headers")
            ):
                req_ctx.request.headers.__setattr__("Authorization", auth_header)

        return await call_next(context)
