# Author: Yiannis Charalambous

"""Keeps track of all the source files that ESBMC-AI is targeting."""

from os import getcwd, walk
from pathlib import Path
from subprocess import PIPE, STDOUT, run, CompletedProcess
from tempfile import NamedTemporaryFile, TemporaryDirectory
from shutil import copytree
from typing import override

from langchain_core.language_models import BaseChatModel
from langchain_core.load.serializable import Serializable
import lizard

from esbmc_ai.log_utils import get_log_level, print_horizontal_line
from esbmc_ai.verifier_output import VerifierOutput


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

    @staticmethod
    def load(file_path: Path, base_path: Path) -> "SourceFile":
        """Creates a new source file by loading the content from disk."""
        if file_path.is_relative_to(base_path):
            file_path = file_path.relative_to(base_path)
        with open(base_path / file_path, "r") as file:
            return SourceFile(file_path, base_path, file.read())

    def __init__(self, file_path: Path, base_path: Path, content: str) -> None:
        if file_path.is_absolute():
            raise ValueError(
                f"SourceFile requires a relative file path, got absolute: {file_path}. "
                f"Use SourceFile.load() to create from absolute paths."
            )
        self.file_path: Path = file_path
        """Relative file path"""
        self.base_path: Path = base_path
        self.content: str = content
        self.verifier_output: VerifierOutput | None = None
        if not self.verify_file_integrity():
            raise ValueError(
                f"File integrity check failed for {self.abs_path}. "
                f"The file content does not match the provided content or the file does not exist."
            )

    @override
    def __repr__(self) -> str:
        return f"SourceFile({self.file_path}, valid={self.verify_file_integrity()})"

    @override
    def __str__(self) -> str:
        return f"SourceFile({self.file_path})"

    @property
    def abs_path(self) -> Path:
        """Returns the abs path"""
        return self.base_path / self.file_path

    @property
    def file_extension(self) -> str:
        """Returns the file extension to the file."""
        return self.file_path.suffix

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
                "--label", str(source_file_2.file_path),  # Label for first file (original)
                "--label", str(self.file_path),  # Label for second file (modified)
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
        if not (self.abs_path.exists() and self.abs_path.is_file()):
            return False

        with open(self.abs_path, "r") as file:
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


class Solution(Serializable):
    """Represents a solution, that is a collection of all the source files that
    ESBMC-AI will be involved in analyzing."""

    @staticmethod
    def from_dir(
        path: Path,
        file_paths: list[Path] | None = None,
        include_dirs: list[Path] | None = None,
    ) -> "Solution":
        """Creates a solution from a base directory. Can append with files manually."""
        path = path.absolute()

        if file_paths:
            return Solution(files=file_paths, base_dir=path, include_dirs=include_dirs)

        result: list[Path] = []
        for dir_path, _, files in walk(path):
            result.extend(Path(dir_path) / file for file in files)

        return Solution(files=result, base_dir=path, include_dirs=include_dirs)

    def __init__(
        self,
        files: list[Path] | None = None,
        base_dir: Path = Path(getcwd()),
        include_dirs: list[Path] | None = None,
    ) -> None:
        """Creates a new solution with a base directory."""
        self.base_dir: Path = base_dir
        self._files: list[SourceFile] = []

        self._include_dirs: dict[Path, list[SourceFile]] = {}
        """Used by C based verifiers."""

        # If files are loaded
        if files:
            for file_path in files:
                if not file_path.is_file():
                    raise ValueError(f"Path is not a file: {file_path}")
                self.load_source_file(file_path)

        if include_dirs:
            for d in include_dirs:
                if not d.is_dir():
                    raise ValueError(f"Path is not a directory: {d}")
                include_files: list[Path] = [p for p in d.rglob("*") if p.is_file()]
                self._include_dirs[d] = [
                    SourceFile.load(file_path=p, base_path=self.base_dir)
                    for p in include_files
                ]

    @property
    def include_dirs(self) -> dict[Path, list[SourceFile]]:
        """Used by C based verifiers."""
        return self._include_dirs

    @property
    def files(self) -> list[SourceFile]:
        """Will return a list of the files. Returns by value."""
        return list(self._files)

    @property
    def files_mapped(self) -> dict[str, SourceFile]:
        """Will return the files mapped to their directory. Returns by value."""
        return {str(source_file.file_path): source_file for source_file in self._files}

    def get_files_by_ext(self, included_ext: list[str]) -> list[SourceFile]:
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

        # Copy individual source files.
        new_file_paths: list[Path] = []
        for source_file in self.files:
            # Handle absolute paths by flattening to just the filename
            if source_file.file_path.is_absolute():
                relative_path = Path(source_file.file_path.name)
            else:
                relative_path = source_file.file_path

            new_file_paths.append(relative_path)
            new_path: Path = base_dir_path / relative_path
            # Write new file
            new_path.parent.mkdir(parents=True, exist_ok=True)
            source_file.save_file(new_path)

        # Copy include directories there
        for d in self.include_dirs:
            new_dir: Path = base_dir_path / d
            copytree(src=d, dst=new_dir, symlinks=True, dirs_exist_ok=True)

        sol = Solution(
            files=new_file_paths,
            base_dir=Path(base_dir_path),
            include_dirs=list(self.include_dirs.keys()),
        )

        return sol

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
        """Add a source file to the solution. If content is provided then it will
        not be loaded."""
        # Get the relative path to the base dir.
        if file_path.is_absolute():
            raise ValueError(
                f"Cannot load absolute path '{file_path}' into Solution. "
                f"All file paths must be relative to the base directory '{self.base_dir}'. "
                f"This is an internal error - paths should be normalized before reaching this point."
            )
        with open(self.base_dir / file_path, "r") as file:
            self._files.append(
                SourceFile(
                    file_path=file_path,
                    base_path=self.base_dir,
                    content=file.read(),
                )
            )

    def get_diff(self, other: "Solution") -> str:
        """Gets the diff with another solution. The following params are used: -ruN"""

        if not self.verify_solution_integrity():
            self.save_temp()

        if not other.verify_solution_integrity():
            other.save_temp()

        cmd = [
            "patch",
            "-ruN",  # (r)ecursive, (u) additional context, (N) treat absent files as empty
            self.base_dir,
            other.base_dir,
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
                f"Diff for {self.base_dir} and {other.base_dir} failed (exit 2)."
            )

        return process.stdout.decode("utf-8")

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
                "-d",  # Change to base dir first
                self.base_dir,
                "-i",  # Flag to specify patch file
                Path(patch_file.name).absolute(),
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
                        f"Patch failed for some files in solution {self.base_dir}"
                    )
                case 2:
                    print_horizontal_line(get_log_level(0))
                    print(
                        f"The patch:\n\n{patch}\n\nThe diff output:\n\n"
                        + process.stdout.decode("utf-8")
                    )
                    raise ValueError(
                        f"Patch failed SERIOUSLY in solution {self.base_dir}"
                    )
