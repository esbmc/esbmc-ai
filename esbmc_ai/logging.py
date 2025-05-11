# Author: Yiannis Charalambous

"""Logging module for verbose printing."""

from os import get_terminal_size

_verbose: int = 0
_enable_horizontal_lines: bool = True
_default_label: str = "ESBMC-AI"


def get_verbose_level() -> int:
    return _verbose


def set_verbose(level: int) -> None:
    """Sets the verbosity level."""
    global _verbose
    _verbose = level


def set_default_label(label: str) -> None:
    global _default_label
    _default_label = label


def set_horizontal_lines(value: bool) -> None:
    global _enable_horizontal_lines
    _enable_horizontal_lines = value


def print_verbose(
    *m: object,
    level: int = 0,
    label: str | None = None,
    post_label: str | None = None,
) -> None:
    """Prints at a verbose level."""
    if _verbose >= level:
        if label is None:
            label = _default_label

        if post_label:
            label = label + " " + post_label

        # If we have a label in the end, then add the double colon.
        if label:
            label += ": "

        print(label, *m)


def log0(*m: object, label: str | None = None, post_label: str | None = None) -> None:
    """Prints at verbose level 0."""
    print_verbose(level=0, label=label, post_label=post_label, *m)


def logv(*m: object, label: str | None = None, post_label: str | None = None) -> None:
    """Level 1 verbose printing."""
    print_verbose(level=1, label=label, post_label=post_label, *m)


def logvv(*m: object, label: str | None = None, post_label: str | None = None) -> None:
    """Level 2 verbose printing."""
    print_verbose(level=2, label=label, post_label=post_label, *m)


def logvvv(*m: object, label: str | None = None, post_label: str | None = None) -> None:
    """Level 3 verbose printing."""
    print_verbose(level=3, label=label, post_label=post_label, *m)


def printv(*m: object) -> None:
    """Level 1 verbose printing."""
    print_verbose(level=1, label="", post_label="", *m)


def printvv(*m: object) -> None:
    """Level 2 verbose printing."""
    print_verbose(level=2, label="", post_label="", *m)


def printvvv(*m: object) -> None:
    """Level 3 verbose printing."""
    print_verbose(level=3, label="", post_label="", *m)


def print_horizontal_line(verbosity: int = 0) -> None:
    """Prints a horizontal line if at a given verbosity level."""
    if _enable_horizontal_lines and _verbose >= verbosity:
        try:
            print("-" * get_terminal_size().columns)
        except OSError:
            print("-" * 80)
