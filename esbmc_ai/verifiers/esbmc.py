# Author: Yiannis Charalambous

import os
import sys
import re
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing_extensions import Any, Optional, override

from esbmc_ai.config import Config
from esbmc_ai.solution import Solution
from esbmc_ai.logging import printvv

from esbmc_ai.base_config import default_scenario
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.base_source_verifier import (
    BaseSourceVerifier,
    SourceCodeParseError,
    VerifierTimedOutException,
)
from esbmc_ai.program_trace import ProgramTrace


class ESBMCOutput(VerifierOutput):
    @override
    def successful(self) -> bool:
        return self.return_code == 0


class ESBMC(BaseSourceVerifier):
    @staticmethod
    def _esbmc_get_violated_property(esbmc_output: str) -> Optional[str]:
        """Gets the violated property line of the ESBMC output."""
        # Find "Violated property:" string in ESBMC output
        lines: list[str] = esbmc_output.splitlines()
        for ix, line in enumerate(lines):
            if "Violated property:" == line:
                return "\n".join(lines[ix : ix + 3])
        return None

    @staticmethod
    def _esbmc_get_counter_example(esbmc_output: str) -> Optional[str]:
        """Gets ESBMC output after and including [Counterexample]"""
        idx: int = esbmc_output.find("[Counterexample]\n")
        if idx == -1:
            return None
        return esbmc_output[idx:]

    @staticmethod
    def _get_esbmc_err_line(esbmc_output: str) -> Optional[int]:
        """Return from the counterexample the line where the error occurs."""
        violated_property: Optional[str] = ESBMC._esbmc_get_violated_property(
            esbmc_output
        )
        if violated_property:
            # Get the line of the violated property.
            pos_line: str = violated_property.splitlines()[1]
            pos_line_split: list[str] = pos_line.split(" ")
            for ix, word in enumerate(pos_line_split):
                if word == "line":
                    # Get the line number
                    return int(pos_line_split[ix + 1])
        return None

    @staticmethod
    def _get_clang_err_line(clang_output: str) -> Optional[int]:
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

    def __init__(self) -> None:
        super().__init__("esbmc", "")
        self.config = Config()

    @property
    def esbmc_path(self) -> Path:
        """Returns the ESBMC path from config."""
        return self.get_config_value("verifier.esbmc.path")

    @override
    def verify_source(
        self,
        solution: Solution,
        params: Optional[list[str]] = None,
        entry_function: str = "main",
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> ESBMCOutput:
        _ = kwargs

        esbmc_params: list[str] = (
            params if params else self.get_config_value("verifier.esbmc.params")
        )

        if "--timeout" in esbmc_params:
            print(
                "Do not add --timeout to ESBMC parameters, instead specify it in its own field."
            )
            sys.exit(1)
        if "--function" in esbmc_params:
            print(
                "Don't add --function to ESBMC parameters, instead specify it in its own field."
            )
            sys.exit(1)

        # Call ESBMC to temporary folder.
        results = self._esbmc(
            solution=solution,
            esbmc_params=esbmc_params,
            entry_function=entry_function,
            timeout=timeout,
        )

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
                value: Optional[str] = self._esbmc_get_violated_property(
                    verifier_output
                )
                if not value:
                    raise ValueError("Not found violated property." + verifier_output)
                return value
            case "ce":
                value: Optional[str] = self._esbmc_get_counter_example(verifier_output)
                if not value:
                    raise ValueError("Not found counterexample.")
                return value
            case "full":
                return verifier_output
            case _:
                raise ValueError(f"Not a valid ESBMC output type: {format}")

    @override
    def get_error_type(self, verifier_output: str) -> str:
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
    def get_error_line(self, verifier_output: str) -> int:
        """Gets the error line of the esbmc_output, regardless if it is a
        counterexample or clang output."""
        line: Optional[int] = self._get_esbmc_err_line(verifier_output)
        if not line:
            line = self._get_clang_err_line(verifier_output)

        assert line
        return line

    @override
    def get_error_line_idx(self, verifier_output: str) -> int:
        """Gets the error line index of the esbmc_output regardless if it is a
        counterexample or clang output."""
        return self.get_error_line(verifier_output) - 1

    def _esbmc(
        self,
        solution: Solution,
        esbmc_params: list[str],
        entry_function: str,
        timeout: Optional[int] = None,
    ):
        """Exit code will be 0 if verification successful, 1 if verification
        failed. And any other number for compilation error/general errors."""

        # Build parameters list
        esbmc_cmd = [str(self.esbmc_path)]
        # ESBMC parameters
        esbmc_cmd.extend(esbmc_params)
        # Files (only accept valid ones)
        esbmc_cmd.extend(
            str(file.file_path) for file in solution.get_files_by_ext(["c", "cpp"])
        )

        # Add timeout suffix for parameter.
        esbmc_cmd.extend(["--timeout", str(timeout) + "s"])
        # Add entry function for parameter.
        esbmc_cmd.extend(["--function", entry_function])

        # Add slack time to process to allow verifier to timeout and end gracefully.
        process_timeout: Optional[float] = timeout + 10 if timeout else None

        # Run ESBMC from solution base_dir and get output
        process: CompletedProcess = run(
            esbmc_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=solution.base_dir,
            timeout=process_timeout,
            check=False,
        )

        output: str = process.stdout.decode("utf-8")
        return process.returncode, output

    @staticmethod
    def _parse_trace_line(
        line: str,
    ) -> Optional[
        tuple[
            Optional[int],
            str,
            int,
            Optional[str],
            Optional[int],
            Optional[str],
        ]
    ]:
        """Parses a line in the trace and returns the following from it:
        * State idx
        * Filename (or None if missing)
        * Line number (or None if missing)
        * Method name (or None if missing)
        * Thread index (or None if missing)
        * Error line (or None if missing)
        """

        method_name: Optional[str] = None
        error_line: Optional[str] = None

        # Get elements that are always present
        base_pattern: str = (
            r"State (\d+) file ([^ ]+) line (\d+)(?:.+) thread (\d+)\n[-]+\n?(.*)?"
        )
        pattern = re.compile(base_pattern, re.DOTALL)
        match = pattern.search(line)
        if match:
            state_number: Optional[int] = (
                int(match.group(1)) if match.group(1) else None
            )
            filename: Optional[str] = match.group(2) if match.group(2) else None
            line_number: Optional[int] = int(match.group(3)) if match.group(3) else None

            thread_index: Optional[int] = (
                int(match.group(4)) if match.group(4) else None
            )

            # Don't return if any of the useful information is missing
            if any(x is None for x in [filename, line_number]):
                return None
            assert filename is not None and line_number is not None
        else:
            raise ValueError(f"Could not find a state match:\n{line}\n")

        # Optional elements
        if " function " in line:
            pattern = re.compile(r"^(:?.+) function [^ ]+(:?.+)\n", re.DOTALL)
            match = pattern.search(line)
            method_name = match.group(1) if match else None

        # If violated property is printed, don't get error line, it's not supported.
        if "Violated property:" not in line:
            pattern = re.compile(r"State (?:.+)\n[-]+\n?(.*)?", re.DOTALL)
            match = pattern.search(line)
            error_line = match.group(1) if match else None

        return (
            state_number,
            filename,
            line_number,
            method_name,
            thread_index,
            error_line,
        )

    @override
    def get_trace(self, solution: Solution, verifier_output: str) -> list[ProgramTrace]:
        # Get [Counterexample] string idx
        ce_idx: int = verifier_output.index("[Counterexample]") + len(
            "[Counterexample]"
        )
        ce_idx_end: int = ce_idx
        traces: list[ProgramTrace] = []

        file_name: str
        line_number: int
        method_name: Optional[str]
        trace_idx: int = 0

        # Get the traces
        while True:
            try:
                ce_idx = verifier_output.index("State ", ce_idx)
                # Get the end of line, which is 3 lines after.
                ce_idx_end = ce_idx
                ce_idx_end = verifier_output.index("\n", ce_idx_end) + 1
                ce_idx_end = verifier_output.index("\n", ce_idx_end) + 1
                ce_idx_end = verifier_output.index("\n", ce_idx_end) + 1
                # Get the information from the state line.
                trace_results = ESBMC._parse_trace_line(
                    verifier_output[ce_idx:ce_idx_end]
                )
                if trace_results:
                    _, file_name, line_number, method_name, _, _ = trace_results

                    traces.append(
                        ProgramTrace(
                            trace_type="statement",
                            trace_index=trace_idx,
                            source_file=solution.files_mapped[file_name],
                            line_idx=line_number,
                            name=method_name if method_name else "",
                        )
                    )

                ce_idx = ce_idx_end + 1
                trace_idx += 1
            except ValueError as e:
                # Gets a value error from the str index method. This is an indicator
                # that we don't have any more traces to parse.
                printvv(e)
                break

        return traces
