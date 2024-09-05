# Author: Yiannis Charalambous

"""# Solution
Keeps track of all the source files that ESBMC-AI is targeting. """

import os
from typing import Optional
from pathlib import Path
from subprocess import PIPE, STDOUT, run, CompletedProcess
from tempfile import NamedTemporaryFile, gettempdir
import lizard


class SourceFile:
    """Represents a source file in the Solution. This class also holds the
    verifier output. Contains methods to manipulate and get information about
    different versions."""

    @classmethod
    def apply_line_patch(
        cls, source_code: str, patch: str, start: int, end: int
    ) -> str:
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

    def __init__(
        self, file_path: Optional[Path], content: str, file_ext: Optional[str] = None
    ) -> None:
        self._file_path: Optional[Path] = file_path
        # Content file shows the file throughout the repair process. Index 0 is
        # the orignial.
        self._content: list[str] = [content]
        # Map _content (each iteration) to esbmc output
        self._esbmc_output: dict[int, str] = {}
        self._file_ext: Optional[str] = file_ext

    @property
    def file_path(self) -> Optional[Path]:
        """Returns the file path of this source file."""
        return self._file_path

    @property
    def file_extension(self) -> str:
        if self._file_ext:
            return self._file_ext
        elif self._file_path:
            return self._file_path.suffix
        else:
            raise ValueError("No extension for SourceFile could be resolved")

    @property
    def initial_content(self) -> str:
        """Returns the initial state content."""
        return self._content[0]

    @property
    def latest_content(self) -> str:
        """Returns the latest available content."""
        return self._content[-1]

    @property
    def content(self) -> tuple[str, ...]:
        """Returns a tuple of the content of this source file."""
        return tuple(self._content)

    @property
    def initial_verifier_output(self) -> str:
        """Returns the first verifier output"""
        assert 0 in self._esbmc_output, "Error: No initial verifier output assigned."
        return self._esbmc_output[0]

    @property
    def latest_verifier_output(self) -> str:
        """Returns the latest verifier output"""
        return self._esbmc_output[len(self._content) - 1]

    @property
    def verifier_output(self) -> dict[int, str]:
        """Returns the verifier outputs of the SourceFile"""
        return self._esbmc_output

    def get_patch(self, index_a: int, index_b: int) -> str:
        """Return diff between `index_a` and `index_b` which are indicies
        referencing the content list."""
        assert len(self._content) > index_a and len(self._content) > index_b

        # Save as temp files
        with (
            NamedTemporaryFile(mode="w", delete=False) as file_a,
            NamedTemporaryFile(mode="w", delete=False) as file_b,
        ):
            file_a.write(self._content[index_a])
            file_a.flush()
            file_b.write(self._content[index_b])
            file_b.flush()

            cmd = ["diff", file_a.name, file_b.name]
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
                    f"Diff for {file_a.name} and {file_b.name} failed (exit 2)."
                )

            return process.stdout.decode("utf-8")

    # Not used
    # def push_line_patch(self, patch: str, start: int, end: int) -> str:
    #     """Calls `apply_line_patch` using the latest source code and then pushes
    #     the new patch to the content."""
    #     new_source: str = SourceFile.apply_line_patch(
    #         source_code=self._content[-1],
    #         patch=patch,
    #         start=start,
    #         end=end,
    #     )
    #     self._content.append(new_source)
    #     return new_source

    def update_content(self, content: str, reset_changes: bool = False) -> None:
        """Ascociates a new version of the content of source code to a file."""
        if reset_changes:
            self._content = [content]
        else:
            self._content.append(content)

    def assign_verifier_output(self, verifier_output: str, index: int = -1) -> None:
        """Assigns verifier output to the ascociated file. If no file is given,
        then assigns to the latest one."""
        if index < 0:
            # Simulate negative indicies like with Lists.
            index = len(self._content) + index
        self._esbmc_output[index] = verifier_output

    def save_file(
        self, file_path: Optional[Path], temp_dir: bool = True, index: int = -1
    ) -> Path:
        """Saves the source code file. If file_path is not specified, it
        will generate an automatic name. If temp_dir is True, it will place
        the saved file in /tmp and use the file_path file name only."""

        file_name: Optional[str] = None
        dir_path: Optional[Path] = None
        if file_path:
            # If file path is a file, then use the name and directory. If not
            # then use a temporary name and just store the folder.
            if file_path.is_file():
                file_name = file_path.name
                dir_path = file_path.parent
            else:
                dir_path = file_path
        else:
            if not self._file_path:
                raise ValueError(
                    "Source code file does not have a name or file_path to save to"
                )
            # Just store the file and use the temp dir.
            file_name = self._file_path.name

        if temp_dir:
            dir_path = Path(gettempdir())

        assert (
            dir_path
        ), "dir_path could not be retrieved: file_path or temp_dir need to be set."

        # Create path if it does not exist.
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

        with NamedTemporaryFile(
            mode="w",
            buffering=-1,
            newline=None,
            suffix=self.file_extension,
            prefix=file_name,
            dir=dir_path,
            delete=False,
        ) as temp_file:
            temp_file.write(self.content[index])
            return Path(temp_file.name)

    @classmethod
    def calculate_cyclomatic_complexity_delta(
        cls,
        source_1: "SourceFile",
        source_2: "SourceFile",
        temp_dir: bool = True,
    ) -> Optional[float]:
        """Calculates the cyclomatic complexity difference between the two source files."""
        try:
            file_1: Path = source_1.save_file(None, temp_dir=temp_dir)
            file_2: Path = source_2.save_file(None, temp_dir=temp_dir)

            cc1 = lizard.analyze_file(file_1)
            cc2 = lizard.analyze_file(file_2)

            return cc1.average_cyclomatic_complexity - cc2.average_cyclomatic_complexity
        except IOError:
            return None


class Solution:
    """Represents a solution, that is a collection of all the source files that
    ESBMC-AI will be involved in analyzing."""

    def __init__(self, files: Optional[list[Path]] = None) -> None:
        files = files if files else []
        self._files: list[SourceFile] = []
        for file_path in files:
            with open(file_path, "r") as file:
                self._files.append(SourceFile(file_path, file.read()))

    @property
    def files(self) -> tuple[SourceFile, ...]:
        """Will return a list of the files. Returns by value."""
        return tuple(self._files)

    @property
    def files_mapped(self) -> dict[Path, SourceFile]:
        """Will return the files mapped to their directory. Returns by value."""
        return {
            source_file.file_path: source_file
            for source_file in self._files
            if source_file.file_path
        }

    def add_source_file(
        self, file_path: Optional[Path], content: Optional[str]
    ) -> None:
        """Add a source file to the solution."""
        if file_path:
            if content:
                self._files.append(SourceFile(file_path, content))
            else:
                with open(file_path, "r") as file:
                    self._files.append(SourceFile(file_path, file.read()))
            return

        if content:
            self._files.append(SourceFile(file_path, content))
            return

        raise RuntimeError("file_path and content cannot be both invalid!")


# Define a global solution (is not required to be used)

_solution: Solution = Solution()


def get_solution() -> Solution:
    """Returns the global default solution object."""
    return _solution
