import os
from typing import Dict, Any


class TimeoutConfig:
    """Configuration class for timeout settings."""

    # Default timeout values (in seconds)
    DEFAULT_REQUEST_TIMEOUT = 60.0
    DEFAULT_CONNECT_TIMEOUT = 10.0
    DEFAULT_TOTAL_TIMEOUT = 300.0  # 5 minutes
    DEFAULT_RETRY_ATTEMPTS = 1
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_POOL_CONNECTIONS = 10
    DEFAULT_POOL_MAXSIZE = 20
    DEFAULT_POOL_TIMEOUT = 30.0

    # Server timeout settings
    DEFAULT_SERVER_TIMEOUT = 300  # 5 minutes for SSE connections
    DEFAULT_KEEP_ALIVE_TIMEOUT = 60  # 1 minute

    @classmethod
    def get_timeout_settings(cls) -> Dict[str, Any]:
        """
        Get timeout settings from environment variables or use defaults.

        Returns:
            Dictionary containing all timeout settings
        """
        return {
            # HTTP Client timeouts
            "request_timeout": float(
                os.getenv("REQUEST_TIMEOUT", cls.DEFAULT_REQUEST_TIMEOUT)
            ),
            "connect_timeout": float(
                os.getenv("CONNECT_TIMEOUT", cls.DEFAULT_CONNECT_TIMEOUT)
            ),
            "total_timeout": float(
                os.getenv("TOTAL_TIMEOUT", cls.DEFAULT_TOTAL_TIMEOUT)
            ),
            # Retry settings
            "retry_attempts": int(
                os.getenv("RETRY_ATTEMPTS", cls.DEFAULT_RETRY_ATTEMPTS)
            ),
            "retry_delay": float(os.getenv("RETRY_DELAY", cls.DEFAULT_RETRY_DELAY)),
            # Connection pool settings
            "pool_connections": int(
                os.getenv("POOL_CONNECTIONS", cls.DEFAULT_POOL_CONNECTIONS)
            ),
            "pool_maxsize": int(os.getenv("POOL_MAXSIZE", cls.DEFAULT_POOL_MAXSIZE)),
            "pool_timeout": float(os.getenv("POOL_TIMEOUT", cls.DEFAULT_POOL_TIMEOUT)),
            # Server settings
            "server_timeout": int(
                os.getenv("SERVER_TIMEOUT", cls.DEFAULT_SERVER_TIMEOUT)
            ),
            "keep_alive_timeout": int(
                os.getenv("KEEP_ALIVE_TIMEOUT", cls.DEFAULT_KEEP_ALIVE_TIMEOUT)
            ),
        }

    @classmethod
    def log_settings(cls, logger=None):
        """Log the current timeout settings."""
        settings = cls.get_timeout_settings()

        if logger:
            logger.info("Current timeout configuration:")
            for key, value in settings.items():
                logger.info(f"  {key}: {value}")                


# Environment variable names for easy reference
ENV_VAR_NAMES = [
    "REQUEST_TIMEOUT",
    "CONNECT_TIMEOUT",
    "TOTAL_TIMEOUT",
    "RETRY_ATTEMPTS",
    "RETRY_DELAY",
    "POOL_CONNECTIONS",
    "POOL_MAXSIZE",
    "POOL_TIMEOUT",
    "SERVER_TIMEOUT",
    "KEEP_ALIVE_TIMEOUT",
]
