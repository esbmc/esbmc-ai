# Author: Yiannis Charalambous

"""Horizontal line logging integrated with Structlog."""

from enum import Enum
from pathlib import Path
import re
from typing import Optional, override
from os import get_terminal_size
import logging
import structlog
from structlog.typing import EventDict

_enable_horizontal_lines: bool = True
_horizontal_line_width: Optional[int] = None
_verbose_level: int = logging.INFO
_logging_format: str = "%(name)s %(message)s"


class LogCategories(Enum):
    NONE = "none"
    ALL = "all"
    SYSTEM = "esbmc_ai"
    VERIFIER = "verifier"
    COMMAND = "command"
    CONFIG = "config"


_largest_cat_len: int = min(10, max(len(cat.value) for cat in LogCategories))
_ansi_escape = re.compile(r"\x1b\[[0-9;]*m")


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


def _init_logging_basic(
    *,
    level: int,
    logging_format: str = _logging_format,
) -> None:
    """Initializes the logging system in basic mode, good for debugging since
    it can easily change the logging_format."""

    structlog.configure(
        processors=[
            # structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _add_category_field,
            _render_prefix_category_to_event,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging level
    logging.basicConfig(
        level=level,
        format=logging_format,
        force=True,
    )


def init_logging(
    *,
    level: int,
    file_handlers: list[logging.Handler] = [],
    init_basic: bool = False,
) -> None:
    """Initializes the logging system.

    Args:
        * level: The level of logging to set for logs to be printed.
        * logging_format: The logging format of the logging module (final step).
        * file_handlers: File handlers to save the logs to. They will be printed
            in plaintext. No colors."""
    global _verbose_level
    _verbose_level = level

    # Configure Structlog with standard logging integration
    structlog.reset_defaults()

    # Suppress noisy libraries after setting global log level.
    for noisy_lib in (
        "httpx",
        "httpcore",
        "urllib",
        "urllib3",
        "openai",
        "anthropic",
        "ollama",
        "huggingface_hub",
    ):
        logging.getLogger(noisy_lib).setLevel(logging.WARN)

    if init_basic:
        _init_logging_basic(level=level)
        return

    structlog.configure(
        processors=[
            # structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _add_category_field,
            _render_prefix_category_to_event,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_formatter: structlog.stdlib.ProcessorFormatter = (
        structlog.stdlib.ProcessorFormatter(
            processors=[
                _filter_keys_processor,
                structlog.dev.ConsoleRenderer(),
            ]
        )
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    formatter: structlog.stdlib.ProcessorFormatter = (
        structlog.stdlib.ProcessorFormatter(
            processors=[
                _filter_keys_processor,
                structlog.dev.ConsoleRenderer(
                    exception_formatter=structlog.dev.plain_traceback,
                    colors=False,
                ),
            ]
        )
    )

    for handler in file_handlers:
        handler.setFormatter(formatter)

    all_handlers: list[logging.Handler] = [console_handler] + file_handlers

    # Configure standard logging level
    logging.basicConfig(
        level=level,
        handlers=all_handlers,
        force=True,
    )


def set_horizontal_lines(value: bool) -> None:
    global _enable_horizontal_lines
    _enable_horizontal_lines = value


def set_horizontal_line_width(value: Optional[int]) -> None:
    global _horizontal_line_width
    _horizontal_line_width = value


def print_horizontal_line(
    level: str | int = "info",
    *,
    char: str = "=",
    category: str = LogCategories.ALL.value,
    width: Optional[int] = None,
    logger: structlog.stdlib.BoundLogger | None = None,
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

    # Determine line width
    if width is not None:
        line_width = width
    elif _horizontal_line_width is not None:
        line_width = _horizontal_line_width
    else:
        try:
            line_width = get_terminal_size().columns
        except OSError:
            line_width = 80 - _largest_cat_len

    if logger is None:
        logger = structlog.get_logger()
        assert logger is not None

    logger.log(level=level_no, event=char * line_width, category=category)


def _render_prefix_category_to_event(
    logger: object, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    If 'category' is present, prefix it to the event message in square brackets,
    then remove 'category' from the event dict.
    """
    _ = logger, method_name
    category_raw: LogCategories | str | None = event_dict.get("category", None)
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
    event_dict.setdefault("category", LogCategories.NONE.value)
    return event_dict


def _filter_keys_processor(
    logger: object, method_name: str, event_dict: EventDict
) -> EventDict:
    _ = logger, method_name, event_dict
    # Remove unwanted keys
    event_dict.pop("_from_structlog", None)
    event_dict.pop("_record", None)
    event_dict.pop("category", None)
    return event_dict


def _strip_ansi_escape_processor(record: logging.LogRecord) -> bool | logging.LogRecord:
    """
    Remove ANSI escape sequences from all string values in the LogRecord.
    """
    for attr, value in list(record.__dict__.items()):
        if isinstance(value, str):
            setattr(record, attr, _ansi_escape.sub("", value))

    args = record.args
    if isinstance(args, tuple):
        record.args = tuple(
            _ansi_escape.sub("", v) if isinstance(v, str) else v for v in args
        )
    elif isinstance(args, dict):
        record.args = {
            k: (_ansi_escape.sub("", v) if isinstance(v, str) else v)
            for k, v in args.items()
        }

    return record


class CategoryFileHandler(logging.Handler):
    """Logger that will save by category."""

    def __init__(
        self,
        base_path: Path,
        append: bool = False,
        skip_uncategorized: bool = False,
    ) -> None:
        super().__init__()
        self.base_path = base_path
        self.append = append
        self.skip_uncategorized = skip_uncategorized
        self.handlers: dict[str, logging.FileHandler] = {}
        self.addFilter(_strip_ansi_escape_processor)

    def emit(self, record: logging.LogRecord) -> None:
        # Grab the category (because of wrap_for_formatter)
        # Try attribute first (for stdlib logging)
        category: str | None = getattr(record, "category", None)

        # If not present, try to get it from record.msg (structlog dict)
        if category is None and isinstance(record.msg, dict):
            category = record.msg.get("category", None)

        # Skip uncategorized if desired
        if (
            not category or category == LogCategories.NONE.value
        ) and self.skip_uncategorized:
            return

        # None category is a catch all
        if not category:
            category = LogCategories.NONE.value

        # Write ALL category
        if category == LogCategories.ALL.value:
            for h in self.handlers.values():
                h.emit(record)
            return

        # Lazily build the per‐category FileHandler
        if category not in self.handlers:
            fn = f"{self.base_path}-{category}.log"
            fh = logging.FileHandler(fn, mode="a" if self.append else "w")
            fh.setFormatter(self.formatter)
            self.handlers[category] = fh

        # Delegate to the per‐category handler
        self.handlers[category].emit(record)


class NameFileHandler(logging.Handler):
    """Logging file handler that will write by logger name."""

    def __init__(
        self, base_path: Path, append: bool = False, skip_unnamed: bool = False
    ) -> None:
        super().__init__()
        self.base_path: Path = base_path
        self.append: bool = append
        self.handlers: dict[str, logging.FileHandler] = {}
        self.skip_unnamed: bool = skip_unnamed
        self.addFilter(_strip_ansi_escape_processor)

    @override
    def emit(self, record: logging.LogRecord) -> None:
        logger_name: str = record.name
        # Write to file (and also to stdout, if desired)
        if logger_name not in self.handlers:
            handler = logging.FileHandler(
                f"{self.base_path}-{logger_name}.log",
                mode="a" if self.append else "w",
            )
            handler.setFormatter(self.formatter)
            self.handlers[logger_name] = handler
        self.handlers[logger_name].emit(record)
