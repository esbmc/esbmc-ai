# Author: Yiannis Charalambous

from enum import Enum
from pathlib import Path
from typing import override
import logging
import re

from esbmc_ai.log_categories import LogCategories

_ansi_escape = re.compile(r"\x1b\[[0-9;]*m")


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
        category: str | Enum | None = getattr(record, "category", None)

        # If not present, try to get it from record.msg (structlog dict)
        if category is None and isinstance(record.msg, dict):
            category = record.msg.get("category", None)

        # Convert to string
        if isinstance(category, Enum):
            category = category.value

        assert isinstance(category, str), f"Category is not string: {category}"

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
            fn: Path = Path(f"{self.base_path}-{category}.log")
            fh: logging.FileHandler = logging.FileHandler(
                fn, mode="a" if self.append else "w"
            )
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
