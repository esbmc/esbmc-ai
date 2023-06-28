# Author: Yiannis Charalambous

"""# Solution
Keeps track of all the source files that ESBMC-AI is targeting."""

_main_source_file: str = ""
_source_files: set[str] = set()


def add_source_file(source_file: str) -> None:
    global _source_files
    _source_files.add(source_file)


def set_main_source_file(source_file: str) -> None:
    add_source_file(source_file)
    global _main_source_file
    _main_source_file = source_file


def get_main_source_file() -> str:
    global _main_source_file
    return _main_source_file


def get_source_files() -> list[str]:
    return list(_source_files)
