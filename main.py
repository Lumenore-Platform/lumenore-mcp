import tools
import sys
import signal
import asyncio
from mcp_instance import mcp
from utils.logger import get_logger

__title__ = "FastMCP and Python3.13 for building massively scalable Lumenore MCP tools"

# Get centralized logger
logger = get_logger()


async def cleanup():
    """Cleanup resources on shutdown."""
    logger.info("Cleaning up resources...")
    try:
        from core.lumenore_analytics import cleanup_lumenore_client

        await cleanup_lumenore_client()
        logger.info("HTTP client session closed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# Global flag for shutdown
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_event.set()


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting Lumenore Analytics MCP Server...")
    logger.info(f"Server configuration: transport=streamable-http, host=0.0.0.0, port=8080")

    try:
        from utils.timeout_config import TimeoutConfig

        # Get server timeout settings
        timeout_settings = TimeoutConfig.get_timeout_settings()

        # Log current configuration
        TimeoutConfig.log_settings(logger)

        logger.info(f"Starting MCP server with {timeout_settings['total_timeout']}s timeout")

        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=8080,
        )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        try:
            # Ensure cleanup runs in a new event loop if needed
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(cleanup())
                else:
                    loop.run_until_complete(cleanup())
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        logger.info("Server shutdown complete")
