import json
import datetime
from mcp_instance import mcp
from core.lumenore_analytics import get_lumenore_client, extract_credentials_from_headers
from core.request_context import get_request_headers
from config import config
from utils.logger import get_logger

logger = get_logger()


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "MCP Server Health Check"
    }
)
async def health_check():
    """
    Comprehensive health check for MCP server status and diagnostics.

    Returns detailed health information including:
    - Server status and configuration
    - Authentication status (server-level vs request-level)
    - Available MCP tools list
    - Lumenore API connectivity
    - Backend services status
    
    This tool requires authentication (via headers or server config) to execute.
    For unauthenticated health checks, use the HTTP /health endpoint instead.
    """
    try:
        health_status = {
            "status": "healthy",
            "server": "Lumenore-Analytics-MCP",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "version": "1.0.0",
            "configuration": {
                "server_url": config.SERVER_URL,
                "base_path": config.BASE_PATH or "/",
                "mcp_endpoint": f"{config.BASE_PATH}/mcp" if config.BASE_PATH else "/mcp",
                "has_server_credentials": config.has_credentials()
            },
            "authentication": {
                "type": "unknown",
                "status": "unknown"
            },
            "mcp_tools": {
                "count": 0,
                "available": []
            },
            "services": {
                "lumenore_client": "unknown", 
                "backend_api": "unknown"
            },
        }

        # Check authentication method being used
        headers = get_request_headers()
        if headers:
            client_id = headers.get("lumenore-client-id") or headers.get("x-lumenore-client-id")
            client_secret = headers.get("lumenore-client-secret") or headers.get("x-lumenore-client-secret")
            has_auth_header = bool(headers.get("authorization"))
            has_client_creds = bool(client_id and client_secret)
            
            if has_auth_header:
                health_status["authentication"]["type"] = "bearer_token"
                health_status["authentication"]["status"] = "request_headers"
                health_status["authentication"]["source"] = "Authorization header"
            elif has_client_creds:
                health_status["authentication"]["type"] = "client_credentials"
                health_status["authentication"]["status"] = "request_headers"
                health_status["authentication"]["source"] = "Client ID/Secret headers"
                health_status["authentication"]["client_id_present"] = bool(client_id)
        
        if config.has_credentials():
            if health_status["authentication"]["status"] == "unknown":
                health_status["authentication"]["type"] = "server_config"
                health_status["authentication"]["status"] = "server_level"
                health_status["authentication"]["source"] = "Environment variables"

        # Get all available MCP tools
        try:
            all_tools = await mcp.list_tools()
            health_status["mcp_tools"]["count"] = len(all_tools)
            health_status["mcp_tools"]["available"] = [
                {
                    "name": tool.name,
                    "title": getattr(tool, "title", tool.name),
                    "description": (tool.description[:80] + "...") if tool.description and len(tool.description) > 80 else tool.description
                }
                for tool in all_tools
            ]
        except Exception as e:
            health_status["mcp_tools"]["error"] = str(e)
            health_status["status"] = "degraded"

        # Use the caller's own credentials (falls back to server-level ones).
        creds = extract_credentials_from_headers(headers or {})

        def _client():
            return get_lumenore_client(
                token=creds["token"],
                client_id=creds["client_id"],
                client_secret=creds["client_secret"],
            )

        # Test lumenore client initialization
        try:
            client = _client()
            health_status["services"]["lumenore_client"] = "healthy"
        except Exception as e:
            health_status["services"]["lumenore_client"] = f"error: {type(e).__name__}"
            health_status["status"] = "degraded"

        # Test backend API connectivity (non-intrusive check)
        try:
            # Try to get dataset metadata as a connectivity test
            client = _client()
            response = await client.call_endpoint(
                endpoint_name="get-domain", method="GET"
            )
            if response and isinstance(response, dict):
                health_status["services"]["backend_api"] = "healthy"
                health_status["connectivity"] = "connected"
            else:
                health_status["services"]["backend_api"] = "unexpected_response"
                health_status["connectivity"] = "partial"

        except Exception as e:
            health_status["services"]["backend_api"] = f"error: {e}"
            health_status["connectivity"] = "disconnected"
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"

        # Determine overall status
        backend_status = health_status["services"]["backend_api"]
        client_status = health_status["services"]["lumenore_client"]

        if "error" in str(backend_status) and "error" in str(client_status):
            health_status["status"] = "unhealthy"
        elif "error" in str(backend_status) or "error" in str(client_status):
            health_status["status"] = "degraded"

        # Return MCP-compliant content format
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(health_status, indent=2)
                }
            ]
        }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "status": "unhealthy",
                        "error": f"Health check failed: {str(e)}",
                        "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
                    }, indent=2)
                }
            ],
            "isError": True
        }
