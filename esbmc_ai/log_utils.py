# Author: Yiannis Charalambous

"""Horizontal line logging integrated with Structlog."""

from enum import Enum
from typing import Any, Optional
from os import get_terminal_size
import logging
import structlog
from structlog.typing import EventDict

_enable_horizontal_lines: bool = True
_horizontal_line_width: Optional[int] = None
_verbose_level: int = logging.INFO


class Categories(Enum):
    SYSTEM = "esbmc_ai"
    VERIFIER = "verifier"
    COMMAND = "command"


_largest_cat_len: int = min(10, max(len(cat.value) for cat in Categories))


def get_log_level(verbosity: int | None = None) -> int:
    """Gets the log level from verbosity, if verbosity is None, then returns the
    global one."""
    if not verbosity:
        return _verbose_level

    # Map verbosity to logging levels
    if verbosity >= 3:
        return logging.DEBUG  # Most verbose
    elif verbosity == 2:
        return logging.INFO
    elif verbosity == 1:
        return logging.WARNING
    else:
        return logging.ERROR  # Default least verbose


def init_logging(level: int = logging.INFO):
    global _verbose_level
    _verbose_level = level

    # Configure Structlog with standard logging integration
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            _render_prefix_category_to_event,
            structlog.dev.ConsoleRenderer(),
            # structlog.processors.KeyValueRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging level
    logging.basicConfig(
        level=level,
        format="%(message)s",
        # format="%(name)s: %(message)s",
    )


def set_horizontal_lines(value: bool) -> None:
    global _enable_horizontal_lines
    _enable_horizontal_lines = value


def set_horizontal_line_width(value: Optional[int]) -> None:
    global _horizontal_line_width
    _horizontal_line_width = value


def print_horizontal_line(
    level: str | int = "info",
    width: Optional[int] = None,
    logger_instance: structlog.stdlib.BoundLogger = structlog.get_logger(),
) -> None:
    """
    Print a horizontal line if logging is enabled for the specified level. Both
    an int of the level or the verbose name could be surprised.
    """
    if not _enable_horizontal_lines:
        return

    # Convert level name to numeric value (e.g., "info" -> logging.INFO)
    level_no: int = (
        getattr(logging, level.upper(), logging.INFO)
        if isinstance(level, str)
        else level
    )

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


def _render_prefix_category_to_event(
    logger: object, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    If 'category' is present, prefix it to the event message in square brackets,
    then remove 'category' from the event dict.
    """
    _ = logger, method_name
    category_raw: Categories | str | None = event_dict.pop("category", None)
    if category_raw is not None:
        category: str = (
            category_raw.value if isinstance(category_raw, Categories) else category_raw
        )

        event = event_dict.get("event")
        # Only add prefix if event is a string
        if isinstance(event, str):
            event_dict["event"] = (
                f"[ {category:<{_largest_cat_len}.{_largest_cat_len}} ] {event}"
            )
    return event_dict
