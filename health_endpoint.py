"""
Health check endpoints for monitoring and deployment verification.
Includes MCP tools information for visibility.
"""
import datetime
from starlette.responses import JSONResponse, Response
from config import config
from mcp_instance import mcp


async def health(request):
    """
    Comprehensive health check endpoint with MCP tools listing.
    No authentication required - safe for load balancers and monitoring.
    """
    try:
        # Get all available tools from MCP
        tools_list = []
        try:
            all_tools = await mcp.list_tools()
            tools_list = [
                {
                    "name": tool.name,
                    "title": getattr(tool, "title", tool.name),
                    "description": (tool.description[:100] + "...") if tool.description and len(tool.description) > 100 else tool.description
                }
                for tool in all_tools
            ]
        except Exception:
            tools_list = [{"error": "Could not fetch tools"}]
        
        return JSONResponse({
            "status": "healthy",
            "service": "Lumenore-Analytics-MCP",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "version": "1.0.0",
            "configuration": {
                "base_path": config.BASE_PATH or "/",
                "mcp_endpoint": f"{config.BASE_PATH}/mcp" if config.BASE_PATH else "/mcp"
            },
            "mcp_info": {
                "protocol_version": "2024-11-05",
                "transport": "streamable-http",
                "tools_count": len(tools_list),
                "tools": tools_list
            }
        })
    except Exception as e:
        return JSONResponse(
            {
                "status": "unhealthy",
                "error": type(e).__name__,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
            },
            status_code=503
        )


async def readiness(request):
    """
    Readiness check - verifies server is ready to accept MCP requests.
    Checks configuration and MCP initialization.
    """
    checks = {
        "config_loaded": True,
        "server_url_configured": bool(config.SERVER_URL),
        "mcp_initialized": mcp is not None,
    }
    
    # Check if tools are accessible
    try:
        tools = await mcp.list_tools()
        checks["tools_available"] = len(tools) > 0
        checks["tools_count"] = len(tools)
    except Exception as e:
        checks["tools_available"] = False
        checks["tools_error"] = type(e).__name__
    
    all_healthy = all(v for k, v in checks.items() if isinstance(v, bool))
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        },
        status_code=status_code
    )


async def liveness(request):
    """
    Liveness check - simple ping to verify process is alive.
    Kubernetes-style probe.
    """
    return Response("OK", status_code=200, media_type="text/plain")
