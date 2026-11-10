#!/bin/bash

# =============================================================================
# Lumenore MCP Server Startup Script
# =============================================================================

# Server Configuration
# Set the Lumenore backend server URL (defaults to preview if not set)
# export SERVER_URL=${SERVER_URL:-"https://your-lumenore-host.example.com"}

# Base Path Configuration
# Leave empty if gateway/reverse proxy strips the prefix (recommended)
# Example: If gateway URL is https://your-lumenore-host.example.com/bridge/lumenore-mcp/mcp
#   - If gateway strips prefix: BASE_PATH=""
#   - If gateway forwards full path: BASE_PATH="/bridge/lumenore-mcp"
# Preserve the value supplied by the deployment. An empty value is intentional
# when ingress strips /bridge/lumenore-mcp before forwarding to this container.
export BASE_PATH="${BASE_PATH:-}"

# Credentials (Optional - for server-level auth fallback)
# Leave empty for multi-tenant deployment where users provide their own credentials
# export LUMENORE_API_KEY=${LUMENORE_API_KEY:-""}
# export LUMENORE_CLIENT_ID=${LUMENORE_CLIENT_ID:-""}
# export LUMENORE_SECRET=${LUMENORE_SECRET:-""}

# Debug Mode
export DEBUG=${DEBUG:-"false"}

# =============================================================================
# Log Configuration
# =============================================================================
echo "=================================================="
echo "Starting Lumenore MCP Server"
echo "=================================================="
echo "SERVER_URL: $SERVER_URL"
echo "BASE_PATH: ${BASE_PATH:-"(empty - root path)"}"
echo "DEBUG: $DEBUG"
echo "=================================================="

# Start the server
python -W ignore::DeprecationWarning main.py
