# Author: Yiannis Charalambous

"""Keeps track of all the source files that ESBMC-AI is targeting. """

from dataclasses import dataclass
from os import getcwd, walk
from typing import Optional
from pathlib import Path
from subprocess import PIPE, STDOUT, run, CompletedProcess
from tempfile import NamedTemporaryFile, TemporaryDirectory
import lizard

from esbmc_ai.verifier_output import VerifierOutput


@dataclass
class SourceFile:
    """Represents a source file in the Solution. This class also holds the
    verifier output. Contains methods to manipulate and get information about
    different versions."""

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

    def __init__(self, file_path: Path, content: str) -> None:
        self.file_path: Path = file_path
        self.content: str = content
        self.verifier_output: Optional[VerifierOutput] = None

    @property
    def file_extension(self) -> str:
        """Returns the file extension to the file."""
        return self.file_path.suffix

    def get_patch(self, source_file_2: "SourceFile") -> str:
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

            cmd = ["diff", file.name, file_2.name]
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

    def save_file(self, file_path: Path) -> Path:
        """Saves the source code file."""

        with open(file_path, "w") as file:
            file.write(self.content)
            return Path(file.name)

    def calculate_cyclomatic_complexity_delta(
        self,
        source_2: "SourceFile",
    ) -> Optional[float]:
        """Calculates the cyclomatic complexity difference between the two source files."""
        try:
            file_1: Path = self.save_temp_file()
            file_2: Path = source_2.save_temp_file()

            cc1 = lizard.analyze_file(file_1)
            cc2 = lizard.analyze_file(file_2)

            return cc1.average_cyclomatic_complexity - cc2.average_cyclomatic_complexity
        except IOError:
            return None


class Solution:
    """Represents a solution, that is a collection of all the source files that
    ESBMC-AI will be involved in analyzing."""

    @staticmethod
    def from_dir(path: Path) -> "Solution":
        """Creates a solution from a directory."""
        result: list[Path] = []
        for dir_path, _, files in walk(path):
            result.extend(Path(dir_path) / file for file in files)

        return Solution(result, path)

    def __init__(
        self,
        files: Optional[list[Path]] = None,
        base_dir: Optional[Path] = None,
    ) -> None:
        """Creates a new solution with a base directory."""
        self.base_dir: Path = base_dir if base_dir else Path(getcwd())
        files = files if files else []
        self._files: list[SourceFile] = []
        for file_path in files:
            with open(file_path, "r") as file:
                self._files.append(SourceFile(file_path, file.read()))

    @property
    def files(self) -> list[SourceFile]:
        """Will return a list of the files. Returns by value."""
        return list(self._files)

    @property
    def files_mapped(self) -> dict[str, SourceFile]:
        """Will return the files mapped to their directory. Returns by value."""
        return {str(source_file.file_path): source_file for source_file in self._files}

    def get_files(self, included_ext: list[str]) -> list[SourceFile]:
        """Gets the files that are only specified in the included extensions. File
        extensions that have a . prefix are trimmed so they still work."""
        return [s for s in self.files if s.file_extension.strip(".") in included_ext]

    def save_temp(self) -> "Solution":
        """Saves the solution in a temporary directory it creates while preserving
        the file structure."""
        with TemporaryDirectory(
            prefix="esbmc-ai", suffix=self.base_dir.name, delete=False
        ) as temp_dir:
            return self.save_solution(Path(temp_dir))

    def save_solution(self, path: Path) -> "Solution":
        """Saves the solution to path, and then returns it. The solution's base
        directory is replaced by the final component of path."""
        base_dir_path: Path = path
        new_file_paths: list[Path] = []
        for source_file in self.files:
            relative_path: Path = source_file.file_path.relative_to(self.base_dir)
            new_path: Path = base_dir_path / relative_path
            # Write new file
            new_file_paths.append(new_path)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            source_file.save_file(new_path)
        return Solution(new_file_paths, Path(base_dir_path))

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
        """Add a source file to the solution. If content is provided then it will
        not be loaded."""
        assert file_path
        with open(file_path, "r") as file:
            self._files.append(SourceFile(file_path, file.read()))


# Define a global solution (is not required to be used)

_solution: Solution = Solution()


def get_solution() -> Solution:
    """Returns the global default solution object."""
    return _solution
