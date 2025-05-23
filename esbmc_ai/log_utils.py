# Author: Yiannis Charalambous

"""Horizontal line logging integrated with Structlog."""

from typing import Optional
from os import get_terminal_size
import logging
import structlog
from structlog.stdlib import LoggerFactory

_enable_horizontal_lines: bool = True
_horizontal_line_width: Optional[int] = None


def init_logging(level: int):
    # Configure Structlog with standard logging integration
    structlog.configure(
        processors=[structlog.processors.KeyValueRenderer()],
        logger_factory=LoggerFactory(),
    )

    # Configure standard logging level
    logging.basicConfig(level=logging.INFO)


def set_horizontal_lines(value: bool) -> None:
    global _enable_horizontal_lines
    _enable_horizontal_lines = value


def set_horizontal_line_width(value: Optional[int]) -> None:
    global _horizontal_line_width
    _horizontal_line_width = value


def print_horizontal_line(
    level: str = "info",
    width: Optional[int] = None,
    logger_instance: structlog.BoundLogger = structlog.get_logger(),
) -> None:
    """Prints a horizontal line if the message would be logged at the given level."""
    if not _enable_horizontal_lines:
        return

    # Convert level name to numeric value (e.g., "info" -> logging.INFO)
    level_no = getattr(logging, level.upper(), logging.INFO)

    # Get the underlying standard logger, fallback to root if None
    std_logger = getattr(logger_instance, "_logger", None)
    if std_logger is None:
        std_logger = logging.getLogger()

    # Check if the level is enabled
    if not std_logger.isEnabledFor(level_no):
        return

    # Determine line width
    if width is not None:
        line_width = width
    elif _horizontal_line_width is not None:
        line_width = _horizontal_line_width
    else:
        try:
            line_width = get_terminal_size().columns
        except OSError:
            line_width = 80

    print("-" * line_width)
