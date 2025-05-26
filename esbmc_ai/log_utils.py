# Author: Yiannis Charalambous

"""Horizontal line logging integrated with Structlog."""

from enum import Enum
from pathlib import Path
from typing import Optional
from os import get_terminal_size
import logging
import structlog
from structlog.typing import EventDict

_enable_horizontal_lines: bool = True
_horizontal_line_width: Optional[int] = None
_verbose_level: int = logging.INFO
_logging_format: str = "%(message)s"  # "%(name)s: %(message)s"


class LogCategories(Enum):
    NONE = "none"
    SYSTEM = "esbmc_ai"
    VERIFIER = "verifier"
    COMMAND = "command"
    CONFIG = "config"


_largest_cat_len: int = min(10, max(len(cat.value) for cat in LogCategories))


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


def init_logging(
    level: int = logging.INFO,
    logging_format: str = _logging_format,
):
    global _verbose_level
    _verbose_level = level

    # Configure Structlog with standard logging integration
    structlog.reset_defaults()

    # Suppress noisy libraries after setting global log level.
    for noisy_lib in ("httpx", "openai", "httpcore"):
        logging.getLogger(noisy_lib).setLevel(logging.WARN)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            _add_category_field,
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
        format=logging_format,
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
    category_raw: LogCategories | str | None = event_dict.pop("category", None)
    if category_raw is not None:
        category: str = (
            category_raw.value
            if isinstance(category_raw, LogCategories)
            else category_raw
        )

        event = event_dict.get("event")
        # Only add prefix if event is a string
        if isinstance(event, str):
            event_dict["event"] = (
                f"[ {category:<{_largest_cat_len}.{_largest_cat_len}} ] {event}"
            )
    return event_dict


def _add_category_field(logger: object, method_name: str, event_dict: EventDict):
    _ = logger, method_name
    # Ensure 'category' is in the event_dict, or set a default
    event_dict.setdefault("category", "none")
    return event_dict


class CategoryFileHandler(logging.Handler):
    """Logger that will save by category."""

    def __init__(self, base_path: Path, skip_uncategorized: bool = False) -> None:
        super().__init__()
        self.base_path: Path = base_path
        self.handlers: dict[str, logging.FileHandler] = {}
        self.skip_uncategorized: bool = skip_uncategorized
        # Handler for stdout
        self.stdout_handler: logging.StreamHandler = logging.StreamHandler()

    def emit(self, record: logging.LogRecord) -> None:
        # Extract the category from the record if present
        category = getattr(record, "category", None)
        # If skipping uncategorized, only emit to stdout
        if (
            not category or category == LogCategories.NONE.value
        ) and self.skip_uncategorized:
            self.stdout_handler.emit(record)
            return
        if not category:
            category = LogCategories.NONE.value
        # Write to file (and also to stdout, if desired)
        if category not in self.handlers:
            handler = logging.FileHandler(f"{self.base_path}-{category}.log")
            handler.setFormatter(self.formatter)
            self.handlers[category] = handler
        self.handlers[category].emit(record)


class NameFileHandler(logging.Handler):
    """Logging file handler that will write by logger name."""

    def __init__(self, base_path: Path, skip_unnamed: bool = False) -> None:
        super().__init__()
        self.base_path: Path = base_path
        self.handlers: dict[str, logging.FileHandler] = {}
        self.skip_unnamed: bool = skip_unnamed
        self.stdout_handler: logging.StreamHandler = logging.StreamHandler()

    def emit(self, record: logging.LogRecord) -> None:
        logger_name: str = record.name
        # Write to file (and also to stdout, if desired)
        if logger_name not in self.handlers:
            handler = logging.FileHandler(f"{self.base_path}-{logger_name}.log")
            handler.setFormatter(self.formatter)
            self.handlers[logger_name] = handler
        self.handlers[logger_name].emit(record)
