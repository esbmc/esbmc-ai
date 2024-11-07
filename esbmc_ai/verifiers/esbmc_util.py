# Author: Yiannis Charalambous

import os
import sys
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import Any, Optional, override

from esbmc_ai.solution import SourceFile
from esbmc_ai.config import default_scenario
from esbmc_ai.verifiers.base_source_verifier import (
    BaseSourceVerifier,
    SourceCodeParseError,
    VerifierOutput,
    VerifierTimedOutException,
)


class ESBMCOutput(VerifierOutput):
    @override
    def successful(self) -> bool:
        return self.return_code == 0


class ESBMCUtil(BaseSourceVerifier):
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
    def get_esbmc_err_line(cls, esbmc_output: str) -> Optional[int]:
        """Return from the counterexample the line where the error occurs."""
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
    def get_esbmc_err_line_idx(cls, esbmc_output: str) -> Optional[int]:
        """Return from the counterexample the line index where the error occurs."""
        line: Optional[int] = cls.get_esbmc_err_line(esbmc_output)
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
    def get_clang_err_line_idx(cls, clang_output: str) -> Optional[int]:
        """Returns the clang error line as a 0-based index."""
        line: Optional[int] = cls.get_clang_err_line(clang_output)
        if line:
            return line - 1
        else:
            return None

    def __init__(self) -> None:
        super().__init__("esbmc")

    @property
    def esbmc_path(self) -> Path:
        return self.get_config_value("path")

    @override
    def verify_source(
        self,
        source_file: SourceFile,
        source_file_iteration: int = -1,
        esbmc_params: list = [],
        auto_clean: bool = False,
        temp_file_dir: Optional[Path] = None,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> ESBMCOutput:
        _ = kwargs
        file_path: Path
        if temp_file_dir:
            file_path = source_file.save_file(
                file_path=Path(temp_file_dir),
                temp_dir=False,
                index=source_file_iteration,
            )
        else:
            file_path = source_file.save_file(
                file_path=None,
                temp_dir=True,
                index=source_file_iteration,
            )

        # Call ESBMC to temporary folder.
        results = self._esbmc(
            path=file_path,
            esbmc_params=esbmc_params,
            timeout=timeout,
        )

        # Delete temp files and path
        if auto_clean:
            # Remove file
            os.remove(file_path)

        # Return
        return_code, output = results
        return ESBMCOutput(
            return_code=return_code,
            output=output,
        )

    @override
    def apply_formatting(self, verifier_output: str, format: str) -> str:
        """Gets the formatted output ESBMC output, based on the esbmc_output_type
        passed."""
        # Check for parsing error
        if "ERROR: PARSING ERROR" in verifier_output:
            # Parsing errors are usually small in nature.
            raise SourceCodeParseError()

        if "ERROR: Timed out" in verifier_output:
            raise VerifierTimedOutException()

        match format:
            case "vp":
                value: Optional[str] = self.esbmc_get_violated_property(verifier_output)
                if not value:
                    raise ValueError("Not found violated property." + verifier_output)
                return value
            case "ce":
                value: Optional[str] = self.esbmc_get_counter_example(verifier_output)
                if not value:
                    raise ValueError("Not found counterexample.")
                return value
            case "full":
                return verifier_output
            case _:
                raise ValueError(f"Not a valid ESBMC output type: {format}")

    @override
    def get_error_type(self, verifier_output: str) -> Optional[str]:
        """Gets the error of violated property, the entire line."""
        # TODO Test me
        # Start search from the marker.
        marker: str = "Violated property:\n"
        violated_property_index: int = verifier_output.rfind(marker) + len(marker)
        from_loc_error_msg: str = verifier_output[violated_property_index:]
        # Find second new line which contains the location of the violated
        # property and that should point to the line with the type of error.
        # In this case, the type of error is the "scenario".
        scenario_index: int = from_loc_error_msg.find("\n")
        scenario: str = from_loc_error_msg[scenario_index + 1 :]
        scenario_end_l_index: int = scenario.find("\n")
        scenario = scenario[:scenario_end_l_index].strip()

        return scenario

    @override
    def get_error_scenario(self, verifier_output: str) -> str:
        scenario: Optional[str] = self.get_error_type(verifier_output)
        if not scenario:
            return default_scenario
        return scenario

    @override
    def get_error_line(self, verifier_output: str) -> Optional[int]:
        """Gets the error line of the esbmc_output, regardless if it is a
        counterexample or clang output."""
        line: Optional[int] = self.get_esbmc_err_line(verifier_output)
        if not line:
            line = self.get_clang_err_line(verifier_output)
        return line

    @override
    def get_error_line_idx(self, verifier_output: str) -> Optional[int]:
        """Gets the error line index of the esbmc_output regardless if it is a
        counterexample or clang output."""
        line: Optional[int] = self.get_esbmc_err_line_idx(verifier_output)
        if not line:
            return self.get_clang_err_line_idx(verifier_output)
        return line - 1

    def _esbmc(
        self,
        path: Path,
        esbmc_params: list,
        timeout: Optional[int] = None,
    ):
        """Exit code will be 0 if verification successful, 1 if verification
        failed. And any other number for compilation error/general errors."""
        # TODO verify_source
        # Build parameters
        esbmc_cmd = [str(self.esbmc_path)]
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
