"""
logger.py — Optional utilities for colored and html-formatted console logging for agents.
"""

import logging
import sys
from typing import Optional, Dict, Any

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
WHITE = "\033[37m"


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter to add colors based on the logger name or an explicit color mapping.
    """

    def __init__(
        self, color_mapping: Optional[Dict[str, str]] = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.color_mapping = color_mapping or {}

    def format(self, record: logging.LogRecord) -> str:
        color = self.color_mapping.get(record.name, WHITE)
        timestamp = self.formatTime(record, self.datefmt)
        prefix = f"{color}{BOLD}[{timestamp}] [{record.name}]{RESET}"

        log_message = f"{prefix} {record.getMessage()}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            if log_message[-1] != "\n":
                log_message += "\n"
            log_message += record.exc_text

        return log_message


def setup_agent_logger(
    name: str, level: int = logging.INFO, color_mapping: Optional[Dict[str, str]] = None
) -> logging.Logger:
    """
    Returns a logger configured with an optional ColoredFormatter.
    Ideal for console-focused AI agent logs.

    Args:
        name: Logger name (e.g. agent name).
        level: Logging level.
        color_mapping: Dict mapping agent names to ANSI color codes.

    Returns:
        logging.Logger
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = ColoredFormatter(color_mapping=color_mapping, datefmt="%H:%M:%S")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
