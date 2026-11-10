import logging
import logging.handlers
import os
import sys
from typing import Optional

from config import config


class LoggerManager:
    """Centralized logging manager for the application.

    Logs go to stderr only (stdout is reserved for the MCP protocol). Set
    LOG_FILE to also write a rotating log file. Never log credentials,
    request headers, queries or response bodies.
    """

    _instance: Optional["LoggerManager"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self._setup_logger()

    def _setup_logger(self):
        self._logger = logging.getLogger("lumenore_analytics")

        log_level = logging.DEBUG if getattr(config, "DEBUG", False) else logging.INFO
        self._logger.setLevel(log_level)

        # Avoid re-adding handlers on re-imports/re-instantiation
        if self._logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        log_file = os.getenv("LOG_FILE", "").strip()
        if log_file:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=3
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

        # Prevent logs from propagating to root (avoid duplicates)
        self._logger.propagate = False
        self._logger.info("Logger initialized (level=%s)", logging.getLevelName(log_level))

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        if self._logger is None:
            self._setup_logger()

        if name:
            return logging.getLogger(f"lumenore_analytics.{name}")
        return self._logger


# Global logger instance
logger_manager = LoggerManager()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logger_manager.get_logger(name)
