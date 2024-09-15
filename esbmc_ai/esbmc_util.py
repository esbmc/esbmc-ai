# Author: Yiannis Charalambous

import os
import sys
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import Optional

from esbmc_ai.solution import SourceFile


class ESBMCUtil:
    @classmethod
    def init(cls, esbmc_path: Path) -> None:
        cls.esbmc_path: Path = esbmc_path

    @classmethod
    def esbmc_get_violated_property(cls, esbmc_output: str) -> Optional[str]:
        """Gets the violated property line of the ESBMC output."""
        # Find "Violated property:" string in ESBMC output
        lines: list[str] = esbmc_output.splitlines()
        for ix, line in enumerate(lines):
            if "Violated property:" == line:
                return "\n".join(lines[ix : ix + 3])
        return None

    @classmethod
    def esbmc_get_counter_example(cls, esbmc_output: str) -> Optional[str]:
        """Gets ESBMC output after and including [Counterexample]"""
        idx: int = esbmc_output.find("[Counterexample]\n")
        if idx == -1:
            return None
        else:
            return esbmc_output[idx:]

    @classmethod
    def esbmc_get_error_type(cls, esbmc_output: str) -> str:
        """Gets the error of violated property, the entire line."""
        # TODO Test me
        # Start search from the marker.
        marker: str = "Violated property:\n"
        violated_property_index: int = esbmc_output.rfind(marker) + len(marker)
        from_loc_error_msg: str = esbmc_output[violated_property_index:]
        # Find second new line which contains the location of the violated
        # property and that should point to the line with the type of error.
        # In this case, the type of error is the "scenario".
        scenario_index: int = from_loc_error_msg.find("\n")
        scenario: str = from_loc_error_msg[scenario_index + 1 :]
        scenario_end_l_index: int = scenario.find("\n")
        scenario = scenario[:scenario_end_l_index].strip()
        return scenario

    @classmethod
    def get_source_code_err_line(cls, esbmc_output: str) -> Optional[int]:
        # Find "Violated property:" string in ESBMC output
        violated_property: Optional[str] = cls.esbmc_get_violated_property(esbmc_output)
        if violated_property:
            # Get the line of the violated property.
            pos_line: str = violated_property.splitlines()[1]
            pos_line_split: list[str] = pos_line.split(" ")
            for ix, word in enumerate(pos_line_split):
                if word == "line":
                    # Get the line number
                    return int(pos_line_split[ix + 1])
        return None

    @classmethod
    def get_source_code_err_line_idx(cls, esbmc_output: str) -> Optional[int]:
        line: Optional[int] = cls.get_source_code_err_line(esbmc_output)
        if line:
            return line - 1
        else:
            return None

    @classmethod
    def get_clang_err_line(cls, clang_output: str) -> Optional[int]:
        """For when the code does not compile, gets the error line reported in the clang
        output. This is useful for `esbmc_output_type single`"""
        lines: list[str] = clang_output.splitlines()
        for line in lines:
            # Find the first line containing a filename along with error.
            line_split: list[str] = line.split(":")
            if len(line_split) < 4:
                continue
            # Check for the filename
            if line_split[0].endswith(".c") and " error" in line_split[3]:
                return int(line_split[1])

        return None

    @classmethod
    def get_clang_err_line_index(cls, clang_output: str) -> Optional[int]:
        line: Optional[int] = cls.get_clang_err_line(clang_output)
        if line:
            return line - 1
        else:
            return None

    @classmethod
    def esbmc(
        cls,
        path: Path,
        esbmc_params: list,
        timeout: Optional[int] = None,
    ):
        """Exit code will be 0 if verification successful, 1 if verification
        failed. And any other number for compilation error/general errors."""
        # Build parameters
        esbmc_cmd = [str(cls.esbmc_path)]
        esbmc_cmd.extend(esbmc_params)
        esbmc_cmd.append(str(path))

        if "--timeout" in esbmc_cmd:
            print(
                'Do not add --timeout to ESBMC parameters, instead specify it in "verifier_timeout".'
            )
            sys.exit(1)

        esbmc_cmd.extend(["--timeout", str(timeout)])

        # Add slack time to process to allow verifier to timeout and end gracefully.
        process_timeout: Optional[float] = timeout + 10 if timeout else None

        # Run ESBMC and get output
        process: CompletedProcess = run(
            esbmc_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            timeout=process_timeout,
        )

        output: str = process.stdout.decode("utf-8")
        return process.returncode, output

    @classmethod
    def esbmc_load_source_code(
        cls,
        source_file: SourceFile,
        source_file_content_index: int,
        esbmc_params: list,
        auto_clean: bool,
        temp_file_dir: Optional[Path] = None,
        timeout: Optional[int] = None,
    ):

        file_path: Path
        if temp_file_dir:
            file_path = source_file.save_file(
                file_path=Path(temp_file_dir),
                temp_dir=False,
                index=source_file_content_index,
            )
        else:
            file_path = source_file.save_file(
                file_path=None,
                temp_dir=True,
                index=source_file_content_index,
            )

        # Call ESBMC to temporary folder.
        results = cls.esbmc(
            path=file_path,
            esbmc_params=esbmc_params,
            timeout=timeout,
        )

        # Delete temp files and path
        if auto_clean:
            # Remove file
            os.remove(file_path)

        # Return
        return results
