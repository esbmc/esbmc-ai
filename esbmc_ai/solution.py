# Author: Yiannis Charalambous

"""# Solution
Keeps track of all the source files that ESBMC-AI is targeting. """

from typing import Optional
from pathlib import Path
from subprocess import PIPE, STDOUT, run, CompletedProcess
from tempfile import NamedTemporaryFile


class SourceFile(object):
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

    def __init__(self, file_path: Optional[Path], content: str) -> None:
        self._file_path: Optional[Path] = file_path
        # Content file shows the file throughout the repair process. Index 0 is
        # the orignial.
        self._content: list[str] = [content]
        # Map _content (each iteration) to esbmc output
        self._esbmc_output: dict[int, str] = {}

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    @property
    def initial_content(self) -> str:
        return self._content[0]

    @property
    def latest_content(self) -> str:
        return self._content[-1]

    @property
    def content(self) -> tuple[str, ...]:
        return tuple(self._content)

    @property
    def initial_verifier_output(self) -> str:
        assert 0 in self._esbmc_output, "Error: No initial verifier output assigned."
        return self._esbmc_output[0]

    @property
    def latest_verifier_output(self) -> str:
        return self._esbmc_output[len(self._content) - 1]

    @property
    def verifier_output(self) -> dict[int, str]:
        return self._esbmc_output

    def get_patch(self, index_a: int, index_b: int) -> str:
        """Return diff between `index_a` and `index_b` which are indicies
        referencing the content list."""
        assert len(self._content) > index_a and len(self._content) > index_b

        # Save as temp files
        file_a = NamedTemporaryFile(mode="w", dir="/tmp")
        file_a.write(self._content[index_a])
        file_b = NamedTemporaryFile(mode="w", dir="/tmp")
        file_b.write(self._content[index_b])

        cmd = ["diff", file_a.name, file_b.name]
        process: CompletedProcess = run(
            cmd,
            stdout=PIPE,
            stderr=STDOUT,
        )

        if process.returncode != 0:
            raise ChildProcessError(
                f"Diff for {index_a} and {index_b} for file {self._file_path} failed with exit code {process.returncode}"
            )

        file_a.close()
        file_b.close()

        return process.stdout.decode("utf-8")

    def push_line_patch(self, patch: str, start: int, end: int) -> str:
        """Calls `apply_line_patch` using the latest source code and then pushes
        the new patch to the content."""
        new_source: str = SourceFile.apply_line_patch(
            source_code=self._content[-1],
            patch=patch,
            start=start,
            end=end,
        )
        self._content.append(new_source)
        return new_source

    def update_content(self, content: str, reset_changes: bool = False) -> None:
        if reset_changes:
            self._content = [content]
        else:
            self._content.append(content)

    def assign_verifier_output(self, verifier_output: str, index: int = -1) -> None:
        if index < 0:
            index = len(self._content) - 1
        self._esbmc_output[index] = verifier_output


class Solution(object):
    def __init__(self, files: list[Path] = []) -> None:
        self._files: list[SourceFile] = []
        for file_path in files:
            with open(file_path, "r") as file:
                self._files.append(SourceFile(file_path, file.read()))

    @property
    def files(self) -> tuple[SourceFile, ...]:
        return tuple(self._files)

    @property
    def files_mapped(self) -> dict[Path, SourceFile]:
        """Will return the files mapped to their directory."""
        return {
            source_file.file_path: source_file
            for source_file in self._files
            if source_file.file_path
        }

    def add_source_file(
        self, file_path: Optional[Path], content: Optional[str]
    ) -> None:
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


def init_solution(solution: Solution) -> Solution:
    global _solution
    _solution = solution
    return _solution


def get_solution() -> Solution:
    return _solution
