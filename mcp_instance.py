from fastmcp import FastMCP
from core.middleware import RawMiddleware

mcp = FastMCP(name="Lumenore-Analytics-MCP", website_url="https://lumenore.com/")
mcp.add_middleware(RawMiddleware())
