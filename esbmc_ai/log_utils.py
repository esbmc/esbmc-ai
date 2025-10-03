# Author: Yiannis Charalambous

"""Horizontal line logging integrated with Structlog."""

from enum import Enum
from os import get_terminal_size
import logging
import structlog
from structlog.typing import EventDict

from esbmc_ai.log_categories import LogCategories

_verbose_level: int = logging.INFO
_logging_format: str = "%(name)s %(message)s"
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

    # Use the basic unformatted logger instead.
    if init_basic:
        _init_logging_basic(level=level)
        return

    structlog.configure(
        processors=[
            # structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _add_category_field,
            _render_prefix_logger_name_to_event,
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


def print_horizontal_line(
    level: str | int = "info",
    *,
    char: str = "=",
    category: Enum | str = LogCategories.ALL,
    width: int | None = None,
    logger: structlog.stdlib.BoundLogger | None = None,
) -> None:
    """
    Print a horizontal line if logging is enabled for the specified level. Both
    an int of the level or the verbose name could be surprised.
    """
    # Import Config locally to avoid circular import
    from esbmc_ai.config import Config

    if not Config().show_horizontal_lines:
        return

    # Convert level name to numeric value (e.g., "info" -> logging.INFO)
    level_no: int = (
        getattr(logging, level.upper(), logging.INFO)
        if isinstance(level, str)
        else level
    )

    # Determine line width
    line_width: int
    if width is not None:
        line_width = width

    else:
        config_hlw: int | None = Config().horizontal_line_width
        if config_hlw is not None:
            line_width = config_hlw
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
    don't remove the key from event dict, delegate it to _filter_keys_processor
    because it's needed by the CategoryFileHandler.
    """
    _ = logger, method_name
    category_raw: Enum | str | None = event_dict.get("category", None)
    if category_raw is not None:
        category: str = (
            category_raw.value if isinstance(category_raw, Enum) else category_raw
        )

        event = event_dict.get("event")
        # Only add prefix if event is a string
        if isinstance(event, str):
            event_dict["event"] = (
                f"[ {category:<{_largest_cat_len}.{_largest_cat_len}} ] {event}"
            )
    return event_dict


def _render_prefix_logger_name_to_event(
    logger: object, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Prefix the logger's name (if available) to the event message in square
    brackets. Then remove the prefix_name from the text.
    """
    _ = method_name

    prepend_name: bool | str = event_dict.get("prefix_name") or False
    if not prepend_name:
        return event_dict

    # Remove
    event_dict.pop("prefix_name", None)

    # Try to get logger's name attribute, fallback to None
    logger_name: str | None = (
        getattr(logger, "name", None)
        if isinstance(prepend_name, bool)
        else prepend_name
    )

    event = event_dict.get("event")
    if logger_name and isinstance(event, str):
        event_dict["event"] = f"[ {logger_name} ] {event}"
    return event_dict


def _add_category_field(
    logger: object, method_name: str, event_dict: EventDict
) -> EventDict:
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
