# Author: Yiannis Charalambous

"""Keeps track of all the source files that ESBMC-AI is targeting."""

from os import walk
from os.path import commonpath
from pathlib import Path
from subprocess import PIPE, STDOUT, run, CompletedProcess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from shutil import copytree
from typing import Any, Literal, override

from langchain_core.language_models import BaseChatModel
from langchain_core.load.serializable import Serializable
from pydantic import Field, PrivateAttr
import lizard
from structlog.stdlib import get_logger

from esbmc_ai.log_utils import LogCategories, get_log_level, print_horizontal_line

_SourceFileFormatStyles = Literal["markdown", "xml", "plain"]


class SolutionIntegrityError(Exception):
    """Raised when the solution disk integrity check fails."""

    def __init__(self, files: list["SourceFile"]):
        assert all(
            isinstance(f, SourceFile) for f in files
        ), "Accept only a list of SourceFiles"
        self.invalid_files: list[SourceFile] = [
            f for f in files if not f.verify_file_integrity()
        ]
        super().__init__(self._build_message())

    def _build_message(self):
        files_list = "\n\t* " + "\n\t* ".join(
            str(f.file_path) for f in self.invalid_files
        )
        return (
            "Solution disk integrity check failed. There are unsaved "
            "changes. Save solution to a temporary location on disk.\n"
            "The following files are invalid:" + files_list
        )


class SourceFile(Serializable):
    """Represents a source file in the Solution. Contains methods to manipulate
    and get information about different versions."""

    file_path: Path = Field(description="Absolute file path")
    content: str = Field(description="File content")

    @staticmethod
    def apply_line_patch(source_code: str, patch: str, start: int, end: int) -> str:
        """Applies a patch to the source code.

        To replace a single line, start and end are equal.

        Args:
            * source_code - The source code to apply the patch to.
            * patch - Can be a line or multiple lines but will replace the start and
            end region defined.
            * start - Line index to mark start of replacement.
            * end - Marks the end of the region where the patch will be applied to.
            End is non-inclusive."""
        assert (
            start <= end
        ), f"start ({start}) needs to be less than or equal to end ({end})"
        lines: list[str] = source_code.splitlines()
        lines = lines[:start] + [patch] + lines[end + 1 :]
        return "\n".join(lines)

    @staticmethod
    def load(file_path: Path) -> "SourceFile":
        """Creates a new source file by loading the content from disk."""
        abs_path = file_path.absolute()
        with open(abs_path, "r") as file:
            return SourceFile(file_path=abs_path, content=file.read())

    def __init__(
        self,
        file_path: Path,
        content: str,
        **kwargs: Any,
    ) -> None:
        # Ensure path is absolute
        if not file_path.is_absolute():
            file_path = file_path.absolute()
        super().__init__(
            file_path=file_path,
            content=content,
            **kwargs,
        )

    @override
    def __repr__(self) -> str:
        return f"SourceFile({self.file_path}, valid={self.verify_file_integrity()})"

    @override
    def __str__(self) -> str:
        return f"SourceFile({self.file_path})"

    @property
    def file_extension(self) -> str:
        """Returns the file extension to the file."""
        return self.file_path.suffix

    @property
    def line_count(self) -> int:
        """Returns the total number of lines in the file."""
        return len(self.content.splitlines())

    def get_num_tokens(
        self,
        ai_model: BaseChatModel,
        lower_idx: int | None = None,
        upper_idx: int | None = None,
    ) -> int:
        """Gets the context size this source code."""
        if not lower_idx:
            lower_idx = 0
        if not upper_idx:
            upper_idx = len(self.content)

        assert lower_idx < upper_idx
        return ai_model.get_num_tokens(self.content[lower_idx:upper_idx])

    def get_diff(self, source_file_2: "SourceFile") -> str:
        """Return diff between two SourceFiles."""
        # Save as temp files
        with (
            NamedTemporaryFile(mode="w", delete=False) as file,
            NamedTemporaryFile(mode="w", delete=False) as file_2,
        ):
            file.write(self.content)
            file.flush()
            file_2.write(source_file_2.content)
            file_2.flush()

            cmd = [
                "diff",
                "-u",  # Adds context around the diff text.
                "--label",
                str(source_file_2.file_path),  # Label for first file (original)
                "--label",
                str(self.file_path),  # Label for second file (modified)
                file_2.name,  # Original file first
                file.name,  # Modified file second
            ]
            process: CompletedProcess = run(
                cmd,
                stdout=PIPE,
                stderr=STDOUT,
                check=False,
            )

            # Exit status is 0 if inputs are the same, 1 if different, 2 if trouble.
            # https://askubuntu.com/questions/698784/exit-code-of-diff
            if process.returncode == 2:
                raise ValueError(
                    f"Diff for {file.name} and {file_2.name} failed (exit 2)."
                )

            return process.stdout.decode("utf-8")

    def save_temp_file(self) -> Path:
        """Saves the file in a temporary directory it creates. The temp file is
        placed in a temporary directory"""
        parent_dir: Path = self.file_path.parent
        with TemporaryDirectory(
            prefix="esbmc-ai", suffix="-" + parent_dir.name
        ) as temp_dir:
            return self.save_file(Path(temp_dir) / self.file_path)

    def save_file(self, abs_path: Path) -> Path:
        """Saves the source code file."""

        with open(abs_path, "w") as file:
            file.write(self.content)
            return Path(file.name)

    def save_diff(self, path: Path, source_file: "SourceFile") -> Path:
        """Saves the source file as a patch of the original."""
        diff: str = self.get_diff(source_file)
        with open(path, "w") as file:
            file.write(diff)
        return path

    def verify_file_integrity(self) -> bool:
        """Verifies that this file matches with the file on disk and does not
        contain any differences."""
        if not (self.file_path.exists() and self.file_path.is_file()):
            return False

        with open(self.file_path, "r") as file:
            content: str = str(file.read())

        return content == self.content

    def calculate_cyclomatic_complexity_delta(
        self,
        source_2: "SourceFile",
    ) -> float | None:
        """Calculates the cyclomatic complexity difference between the two source files."""
        try:
            file_1: Path = self.save_temp_file()
            file_2: Path = source_2.save_temp_file()

            cc1 = lizard.analyze_file(file_1)
            cc2 = lizard.analyze_file(file_2)

            return cc1.average_cyclomatic_complexity - cc2.average_cyclomatic_complexity
        except IOError:
            return None

    @property
    def formatted(self) -> str:
        """Default markdown formatting - most common use case for LangChain templates."""
        return self.format_as()

    def format_as(
        self,
        style: _SourceFileFormatStyles = "markdown",
        include_line_numbers: bool = False,
        max_lines: int | None = None,
        working_dir: Path | None = None,
    ) -> str:
        """Flexible formatting with options for use in LangChain prompts.

        Args:
            style: Format style - "markdown", "xml", or "plain"
            include_line_numbers: Add line numbers to the content
            max_lines: Limit content to first N lines (with truncation notice)

        Returns:
            Formatted string representation of the source file
        """
        lang = self.file_extension.strip(".")
        content = self.content

        # Truncate if needed
        if max_lines:
            lines = content.splitlines()[:max_lines]
            content = "\n".join(lines)
            if len(self.content.splitlines()) > max_lines:
                content += (
                    f"\n... ({len(self.content.splitlines()) - max_lines} more lines)"
                )

        # Add line numbers if requested
        if include_line_numbers:
            lines = content.splitlines()
            content = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

        # Format based on style
        show_path: Path = (
            self.file_path.relative_to(working_dir) if working_dir else self.file_path
        )
        if style == "markdown":
            result = f"{show_path}\n```{lang}\n{content}\n```"
        elif style == "xml":
            result = f"<file path='{show_path}'>\n{content}\n</file>"
        elif style == "plain":
            result = f"File: {show_path}\n{content}"

        return result


class Solution(Serializable):
    """Represents a solution, that is a collection of all the source files that
    ESBMC-AI will be involved in analyzing."""

    _files: list[SourceFile] = PrivateAttr(default_factory=list)
    _include_dirs: list[Path] = PrivateAttr(default_factory=list)

    @staticmethod
    def from_paths(
        *paths: Path,
        include_dirs: list[Path] | None = None,
    ) -> "Solution":
        """Creates a solution from one or more paths (files or directories).

        Directories are scanned recursively for all files.

        Args:
            *paths: One or more file or directory paths
            include_dirs: Optional include directories for C/C++ compilation

        Example:
            Solution.from_paths(Path("file1.c"), Path("file2.c"))
            Solution.from_paths(Path("/project"))
            Solution.from_paths(Path("src"), Path("tests/test.c"))
        """
        result: list[Path] = []

        for path in paths:
            abs_path = path.absolute()
            if abs_path.is_file():
                result.append(abs_path)
            elif abs_path.is_dir():
                for dir_path, _, files in walk(abs_path):
                    result.extend(Path(dir_path) / file for file in files)
            else:
                raise ValueError(
                    f"Path does not exist or is neither file nor directory: {path}"
                )

        return Solution(files=result, include_dirs=include_dirs)

    def __init__(
        self,
        files: list[Path] | None = None,
        include_dirs: list[Path] | None = None,
        **kwargs: Any,
    ) -> None:
        """Creates a new solution from file paths."""
        super().__init__(**kwargs)

        # Initialize private attributes
        self._files = []
        self._include_dirs = []

        # If files are loaded
        if files:
            for file_path in files:
                # Convert to absolute path
                abs_path = (
                    file_path if file_path.is_absolute() else file_path.absolute()
                )
                if not abs_path.is_file():
                    raise ValueError(f"Path is not a file: {file_path}")
                self._files.append(SourceFile.load(abs_path))

        if include_dirs:
            for d in include_dirs:
                abs_dir = d if d.is_absolute() else d.absolute()
                if not abs_dir.is_dir():
                    raise ValueError(f"Path is not a directory: {d}")
                self._include_dirs.append(abs_dir)

    @property
    def include_dirs(self) -> list[Path]:
        """Include directories for C based verifiers."""
        return list(self._include_dirs)

    @property
    def files(self) -> list[SourceFile]:
        """Will return a list of the files. Returns by value."""
        return list(self._files)

    @property
    def working_dir(self) -> Path:
        """Computes the common parent directory of all files."""
        if not self._files:
            return Path.cwd()

        paths = [str(f.file_path) for f in self._files]
        common = commonpath(paths)

        # If only one file, commonpath returns the file itself, so use parent
        return Path(common).parent if len(paths) == 1 else Path(common)

    def get_files_by_ext(self, included_ext: list[str]) -> list[SourceFile]:
        """Gets the files that are only specified in the included extensions. File
        extensions that have a . prefix are trimmed so they still work."""
        return [s for s in self.files if s.file_extension.strip(".") in included_ext]

    @property
    def files_list_formatted(self) -> str:
        """Bullet point list of all files - useful for LangChain templates."""
        return "\n".join(f"- {f.file_path}" for f in self.files)

    @property
    def formatted(self) -> str:
        """Default: all files formatted with markdown - useful for LangChain templates."""
        return self.format_as()

    def format_as(
        self,
        style: _SourceFileFormatStyles = "markdown",
        include_line_numbers: bool = False,
        max_lines_per_file: int | None = None,
        separator: str = "\n\n---\n\n",
    ) -> str:
        """Format all source files with options for use in LangChain prompts.

        Args:
            style: Format style - "markdown", "xml", or "plain"
            include_line_numbers: Add line numbers to the content
            max_lines_per_file: Limit each file's content to first N lines
            separator: String to separate files (default: horizontal rule)

        Returns:
            Formatted string representation of all source files
        """
        formatted_files = [
            f.format_as(
                style=style,
                include_line_numbers=include_line_numbers,
                max_lines=max_lines_per_file,
            )
            for f in self.files
        ]
        return separator.join(formatted_files)

    def save_temp(self) -> "Solution":
        """Saves the solution in a temporary directory it creates while preserving
        the file structure."""
        with TemporaryDirectory(
            prefix="esbmc-ai-", suffix="-" + self.working_dir.name, delete=False
        ) as temp_dir:
            return self.save_solution(Path(temp_dir))

    def save_solution(self, path: Path) -> "Solution":
        """Saves the solution to path, preserving relative structure.

        Files are saved relative to their common parent (working_dir)."""
        get_logger().bind(category=LogCategories.SYSTEM).info(
            f"Saving solution to {path}"
        )

        dest_path: Path = path.absolute()
        dest_path.mkdir(parents=True, exist_ok=True)

        # Get common parent to preserve relative structure
        common_parent: Path = self.working_dir

        # Copy individual source files preserving structure
        new_file_paths: list[Path] = []
        for source_file in self.files:
            # Get path relative to common parent
            relative_path = source_file.file_path.relative_to(common_parent)
            new_path: Path = dest_path / relative_path

            # Write new file
            new_path.parent.mkdir(parents=True, exist_ok=True)
            source_file.save_file(new_path)
            new_file_paths.append(new_path)

        # Copy include directories
        new_include_dirs: list[Path] = []
        for d in self.include_dirs:
            try:
                # Preserve relative structure from working_dir for project include dirs
                relative_path = d.relative_to(common_parent)
                new_dir: Path = dest_path / relative_path
            except ValueError:
                # If include_dir is outside working_dir (e.g., /usr/include),
                # use basename (this maintains backward compatibility for external includes)
                new_dir: Path = dest_path / d.name
            copytree(src=d, dst=new_dir, symlinks=True, dirs_exist_ok=True)
            new_include_dirs.append(new_dir)

        return Solution(
            files=new_file_paths,
            include_dirs=new_include_dirs,
        )

    def verify_solution_integrity(self) -> bool:
        """Verifies if the content of the solution match with the files on disk.
        If that's not the case, then the solution should be saved on disk before
        any operations such as using verifiers that require on-disk solution
        access to work."""

        return all(f.verify_file_integrity() for f in self._files)

    def add_source_file(self, source_file: SourceFile) -> None:
        """Adds a source file to the solution."""
        self._files.append(source_file)

    def add_source_files(self, source_files: list[SourceFile]) -> None:
        """Adds multiple source files to the solution"""
        for f in source_files:
            self._files.append(f)

    def load_source_files(self, file_paths: list[Path]) -> None:
        """Loads multiple source files from disk."""
        for f in file_paths:
            assert isinstance(f, Path), f"Invalid type: {type(f)}"
            if f.is_dir():
                for path in f.glob("**/*"):
                    if path.is_file() and path.name:
                        self.load_source_file(path)
            else:
                self.load_source_file(f)

    def load_source_file(self, file_path: Path) -> None:
        """Add a source file to the solution by loading it from disk."""
        abs_path = file_path if file_path.is_absolute() else file_path.absolute()
        self._files.append(SourceFile.load(abs_path))

    def get_diff(self, other: "Solution") -> str:
        """Gets the diff with another solution. The following params are used: -ruN"""

        if not self.verify_solution_integrity():
            self.save_temp()

        if not other.verify_solution_integrity():
            other.save_temp()

        cmd = [
            "diff",
            "-ruN",  # (r)ecursive, (u) additional context, (N) treat absent files as empty
            str(self.working_dir),
            str(other.working_dir),
        ]

        process: CompletedProcess = run(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
            check=False,
        )

        # Exit status is 0 if inputs are the same, 1 if different, 2 if trouble.
        # https://askubuntu.com/questions/698784/exit-code-of-diff
        if process.returncode == 2:
            raise ValueError(
                f"Diff for {self.working_dir} and {other.working_dir} failed (exit 2)."
            )

        return process.stdout.decode("utf-8")

    def save_diff(self, path: Path, solution: "Solution") -> Path:
        """Saves the solution as a patch of the original."""
        diff: str = self.get_diff(solution)
        with open(path, "w") as file:
            file.write(diff)
        return path

    def resolve(self, file: SourceFile | Path) -> SourceFile | None:
        """Resolve a Path or SourceFile to its corresponding SourceFile in the solution.

        Args:
            file: Either a SourceFile instance or a Path (absolute or relative)

        Returns:
            The SourceFile if found, None otherwise
        """
        if isinstance(file, SourceFile):
            search_path = file.file_path
        else:
            # Convert to absolute path for comparison
            search_path = Path(file).absolute()

        for f in self._files:
            if f.file_path == search_path:
                return f
        return None

    def __contains__(self, file: SourceFile | Path) -> bool:
        """Check if a file is part of this solution. Enables 'in' operator.

        Args:
            file: Either a SourceFile instance or a Path (absolute or relative)

        Returns:
            True if the file is in the solution, False otherwise
        """
        return self.resolve(file) is not None

    def get_file(self, path: Path) -> SourceFile:
        """Get a SourceFile by path, raising KeyError if not found.

        Args:
            path: Either an absolute or relative Path

        Returns:
            The SourceFile

        Raises:
            KeyError: If the path is not in the solution
        """
        result = self.resolve(path)
        if result is None:
            raise KeyError(f"Path not found in solution: {path}")
        return result

    def __add__(self, other: "Solution") -> "Solution":
        """Combine two solutions by merging their files and include directories.

        Warning: This will not save them or change their location! You should
        save them to a common directory if you are trying to "merge" them...

        Args:
            other: Another Solution instance to combine with this one

        Returns:
            A new Solution containing all files and include_dirs from both solutions

        Example:
            solution_c = solution_a + solution_b
        """
        if not isinstance(other, Solution):
            return NotImplemented

        return Solution(
            # Combine files - create new list to avoid modifying originals
            files=[source_file.file_path for source_file in self._files + other._files],
            # Combine include_dirs - deduplicate by converting to set and back
            include_dirs=list(set(self._include_dirs + other._include_dirs)),
        )

    def patch_solution(self, patch: str) -> None:
        """Patches the solution using the patch command."""
        if not self.verify_solution_integrity():
            raise SolutionIntegrityError(self.files)

        # Save as temp files
        with NamedTemporaryFile(mode="w", delete=False) as patch_file:
            patch_file.write(patch)
            patch_file.flush()

            cmd = [
                "patch",
                "-d",  # Change to working dir first
                str(self.working_dir),
                "-i",  # Flag to specify patch file
                str(Path(patch_file.name).absolute()),
            ]

            process: CompletedProcess = run(
                cmd,
                stdout=PIPE,
                stderr=STDOUT,
                check=False,
            )

            # patch's exit status is 0 if all hunks are applied successfully,
            # 1 if some  hunks  cannot  be applied  or there were merge
            # conflicts, and 2 if there is more serious trouble.
            match process.returncode:
                case 1:
                    print_horizontal_line(get_log_level(0))
                    print(
                        f"The patch:\n\n{patch}\n\nThe diff output:\n\n"
                        + process.stdout.decode("utf-8")
                    )
                    raise ValueError(
                        f"Patch failed for some files in solution {self.working_dir}"
                    )
                case 2:
                    print_horizontal_line(get_log_level(0))
                    print(
                        f"The patch:\n\n{patch}\n\nThe diff output:\n\n"
                        + process.stdout.decode("utf-8")
                    )
                    raise ValueError(
                        f"Patch failed SERIOUSLY in solution {self.working_dir}"
                    )
