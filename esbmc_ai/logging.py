# Author: Yiannis Charalambous

"""Logging module for verbose printing."""

from os import get_terminal_size

_verbose: int = 0


def get_verbose_level() -> int:
    return _verbose


def set_verbose(level: int) -> None:
    """Sets the verbosity level."""
    global _verbose
    _verbose = level


def printv(*m: object) -> None:
    """Level 1 verbose printing."""
    if _verbose > 0:
        print(*m)


def printvv(*m: object) -> None:
    """Level 2 verbose printing."""
    if _verbose > 1:
        print(*m)


def printvvv(*m: object) -> None:
    """Level 3 verbose printing."""
    if _verbose > 2:
        print(*m)


def print_horizontal_line(verbosity: int) -> None:
    if _verbose >= verbosity:
        try:
            print("-" * get_terminal_size().columns)
        except OSError:
            pass
