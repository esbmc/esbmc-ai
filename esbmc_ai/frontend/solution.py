# Author: Yiannis Charalambous

"""# Solution
Keeps track of all the source files that ESBMC-AI is targeting."""

from typing import NamedTuple


class SourceFile(NamedTuple):
    file_path: str
    content: str


_main_source_file: SourceFile = SourceFile("", "")
_source_files: set[SourceFile] = set()


def add_source_file(source_file: SourceFile) -> None:
    global _source_files
    _source_files.add(source_file)


def set_main_source_file(source_file: SourceFile) -> None:
    add_source_file(source_file)
    global _main_source_file
    _main_source_file = source_file


def get_main_source_file_path() -> str:
    global _main_source_file
    return _main_source_file.file_path


def get_main_source_file() -> SourceFile:
    global _main_source_file
    return _main_source_file


def get_source_files() -> list[SourceFile]:
    global _source_files
    return list(_source_files)
