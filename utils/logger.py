import logging
import sys
from typing import Optional

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Agent Colors Mapping
AGENT_COLORS = {
    "PokemonAgent": CYAN,
    "APIAgent": MAGENTA,
    "RAGAgent": GREEN,
    "TechDataAgent": YELLOW,
    "WebSearchAgent": RED,
    "BaseAgent": WHITE,
}


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter to add colors based on the logger name (Agent Name).
    """

    def format(self, record):
        # Get color for the agent
        color = AGENT_COLORS.get(record.name, WHITE)

        # Format the timestamp
        timestamp = self.formatTime(record, self.datefmt)

        # Create the colored prefix: [Timestamp] [AgentName]
        prefix = f"{color}{BOLD}[{timestamp}] [{record.name}]{RESET}"

        # Format the message
        # We can also colorize the level name if needed, but let's keep it simple for now
        log_message = f"{prefix} {record.getMessage()}"

        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            if log_message[-1] != "\n":
                log_message = log_message + "\n"
            log_message = log_message + record.exc_text

        return log_message


# CSS Colors for HTML Logs
AGENT_CSS_COLORS = {
    "PokemonAgent": "#06b6d4",  # Cyan
    "APIAgent": "#d946ef",  # Magenta
    "RAGAgent": "#22c55e",  # Green
    "TechDataAgent": "#eab308",  # Yellow
    "WebSearchAgent": "#ef4444",  # Red
    "BaseAgent": "#e5e7eb",  # White
}


class HtmlFormatter(logging.Formatter):
    """
    Formatter that outputs HTML spans for colors.
    """

    def format(self, record):
        color = AGENT_CSS_COLORS.get(record.name, "#e5e7eb")
        timestamp = self.formatTime(record, self.datefmt)

        # Escape HTML characters in message to prevent injection/broken layout
        import html

        msg_content = html.escape(record.getMessage())

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            msg_content += f"\n{html.escape(record.exc_text)}"

        # HTML Structure
        # We use a slight background for the prefix to make it stand out
        prefix_html = f'<span style="color: {color}; font-weight: bold;">[{timestamp}] [{record.name}]</span>'

        return f"{prefix_html} {msg_content}<br>"


# Global Log Buffer
LOG_BUFFER = []


class BufferedHandler(logging.Handler):
    """
    Handler that buffers log records in memory.
    """

    def emit(self, record):
        try:
            msg = self.format(record)
            LOG_BUFFER.append(msg)
            # Keep buffer size reasonable (e.g., last 1000 lines)
            if len(LOG_BUFFER) > 1000:
                LOG_BUFFER.pop(0)
        except Exception:
            self.handleError(record)


def get_log_buffer() -> str:
    """
    Returns the current content of the log buffer as a single HTML string.
    Wraps it in a scrollable div.
    """
    content = "".join(LOG_BUFFER)
    # Wrap in a container styling
    return f"""
    <div style="
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 14px;
        line-height: 1.4;
        white-space: pre-wrap;
        height: 500px;
        overflow-y: auto;
        background-color: #0d1117;
        color: #c9d1d9;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #30363d;
    ">
    {content}
    </div>
    """


def setup_logger(
    name: str, level: int = logging.INFO, log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configures and returns a logger with a standard format.

    Args:
        name: The name of the logger (usually __name__).
        level: The logging level.
        log_file: Optional path to a log file.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    # prevent adding multiple handlers if setup is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Use ColoredFormatter for console
    console_formatter = ColoredFormatter(datefmt="%H:%M:%S")

    # File Formatter (No colors) for file
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # HTML Formatter for UI Buffer
    html_formatter = HtmlFormatter(datefmt="%H:%M:%S")

    # Stream Handler (Stdout)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(console_formatter)
    logger.addHandler(stream_handler)

    # File Handler (Optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Buffered Handler (For UI)
    buffered_handler = BufferedHandler()
    buffered_handler.setLevel(level)
    buffered_handler.setFormatter(html_formatter)  # Use HTML formatter
    logger.addHandler(buffered_handler)

    return logger
