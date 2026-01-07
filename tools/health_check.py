import json
from mcp_instance import mcp
from core.lumenore_analytics import get_lumenore_client
from utils.logger import get_logger

logger = get_logger()


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "title": "Analyze Trend Data"
    }
)
async def health_check():
    """
    Health check endpoint to verify server connectivity and status.

    Returns comprehensive health status information including server status,
    connection status, and basic diagnostics in MCP-compliant format.
    """
    try:
        # Test basic server functionality
        health_status = {
            "status": "healthy",
            "server": "Lumenore-Analytics-MCP",
            "timestamp": None,
            "connectivity": "unknown",
            "services": {"lumenore_client": "unknown", "backend_api": "unknown"},
        }

        # Add timestamp
        import datetime

        health_status["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"

        # Test lumenore client initialization
        try:
            client = get_lumenore_client()
            health_status["services"]["lumenore_client"] = "healthy"
        except Exception as e:
            health_status["services"]["lumenore_client"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        # Test backend API connectivity (non-intrusive check)
        try:
            # Try to get dataset metadata as a connectivity test
            client = get_lumenore_client()
            
            # Make request with default timeout settings
            response = await client.make_request(
                endpoint_name="get-domain", method="GET"
            )
            if response and isinstance(response, dict):
                health_status["services"]["backend_api"] = "healthy"
                health_status["connectivity"] = "connected"
            else:
                health_status["services"]["backend_api"] = "unexpected_response"
                health_status["connectivity"] = "partial"

        except Exception as e:
            health_status["services"]["backend_api"] = f"error: {str(e)}"
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
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    }, indent=2)
                }
            ],
            "isError": True
        }
