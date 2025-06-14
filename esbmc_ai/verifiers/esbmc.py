# Author: Yiannis Charalambous

import signal
import sys
import re
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
import structlog
from typing_extensions import Any, override

from esbmc_ai.solution import Solution

from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.program_trace import ProgramTrace


class ESBMCOutput(VerifierOutput):
    @override
    def successful(self) -> bool:
        return self.return_code == 0

    def _esbmc_get_violated_property(self) -> str | None:
        """Gets the violated property line of the ESBMC output."""
        # Find "Violated property:" string in ESBMC output
        lines: list[str] = self.output.splitlines()
        for ix, line in enumerate(lines):
            if "Violated property:" == line:
                return "\n".join(lines[ix : ix + 3])
        return None

    def _esbmc_get_counter_example(self) -> str | None:
        """Gets ESBMC output after and including [Counterexample]"""
        idx: int = self.output.find("[Counterexample]\n")
        if idx == -1:
            return None
        return self.output[idx:]

    def _get_esbmc_err_line(self) -> int | None:
        """Return from the counterexample the line where the error occurs."""
        violated_property: str | None = self._esbmc_get_violated_property()
        if violated_property:
            # Get the line of the violated property.
            pos_line: str = violated_property.splitlines()[1]
            pos_line_split: list[str] = pos_line.split(" ")
            for ix, word in enumerate(pos_line_split):
                if word == "line":
                    # Get the line number
                    return int(pos_line_split[ix + 1])
        return None

    def _get_clang_err_line(self) -> int | None:
        """For when the code does not compile, gets the error line reported in the clang
        output. This is useful for `esbmc_output_type single`"""
        lines: list[str] = self.output.splitlines()
        for line in lines:
            # Find the first line containing a filename along with error.
            line_split: list[str] = line.split(":")
            if len(line_split) < 4:
                continue
            # Check for the filename
            if line_split[0].endswith(".c") and " error" in line_split[3]:
                return int(line_split[1])

        return None

    @override
    def get_error_line(self) -> int:
        """Gets the error line of the esbmc_output, regardless if it is a
        counterexample or clang output."""
        line: int | None = self._get_esbmc_err_line()
        if not line:
            line = self._get_clang_err_line()

        assert line
        return line

    @override
    def get_error_line_idx(self) -> int:
        """Gets the error line index of the esbmc_output regardless if it is a
        counterexample or clang output."""
        return self.get_error_line() - 1

    @override
    def get_error_type(self) -> str:
        """Gets the error of violated property, the entire line."""
        # TODO Test me
        # Start search from the marker.
        marker: str = "Violated property:\n"
        violated_property_index: int = self.output.rfind(marker) + len(marker)
        from_loc_error_msg: str = self.output[violated_property_index:]
        # Find second new line which contains the location of the violated
        # property and that should point to the line with the type of error.
        # In this case, the type of error is the "scenario".
        scenario_index: int = from_loc_error_msg.find("\n")
        scenario: str = from_loc_error_msg[scenario_index + 1 :]
        scenario_end_l_index: int = scenario.find("\n")
        scenario = scenario[:scenario_end_l_index].strip()

        return scenario

    @override
    def get_stack_trace(self) -> str:
        try:
            start_idx: int = self.output.index("Stack trace:")
            end_idx: int = self.output.index("\n\n\n", start_idx)
        except ValueError:
            return ""

        return self.output[start_idx:end_idx]

    @staticmethod
    def _parse_trace_line(
        line: str,
    ) -> (
        tuple[
            int | None,
            str,
            int,
            str | None,
            int | None,
            str | None,
        ]
        | None
    ):
        """Parses a line in the trace and returns the following from it:
        * State idx
        * Filename (or None if missing)
        * Line number (or None if missing)
        * Method name (or None if missing)
        * Thread index (or None if missing)
        * Error line (or None if missing)
        """

        method_name: str | None = None
        error_line: str | None = None

        # Get elements that are always present
        base_pattern: str = (
            r"State (\d+) file ([^ ]+) line (\d+)(?:.+) thread (\d+)\n[-]+\n?(.*)?"
        )
        pattern = re.compile(base_pattern, re.DOTALL)
        match = pattern.search(line)
        if match:
            state_number: int | None = int(match.group(1)) if match.group(1) else None
            filename: str | None = match.group(2) if match.group(2) else None
            line_number: int | None = int(match.group(3)) if match.group(3) else None

            thread_index: int | None = int(match.group(4)) if match.group(4) else None

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
    def get_trace(
        self,
        solution: Solution,
        include_libs: bool = False,
        add_missing_source: bool = False,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> list[ProgramTrace]:
        """Gets the trace from the CE of the verifier output. Uses "[Counterexample]"
        as the starting anchor. If include_libs is True, then the files that are
        outside of the base path will be included, mainly libraries and external files.
        If add_missing_source is True will add source code that was specified as an
        include libs but not in the files."""
        # Get [Counterexample] string idx
        ce_idx: int = self.output.index("[Counterexample]") + len("[Counterexample]")
        ce_idx_end: int = ce_idx
        traces: list[ProgramTrace] = []

        if not add_missing_source:
            solution = solution.save_temp()

        file_name: str
        line_number: int
        method_name: str | None
        trace_idx: int = 0

        # Get the traces
        while True:
            try:
                ce_idx = self.output.index("State ", ce_idx)
                # Get the end of line, which is 3 lines after.
                ce_idx_end = ce_idx
                ce_idx_end = self.output.index("\n", ce_idx_end) + 1
                ce_idx_end = self.output.index("\n", ce_idx_end) + 1
                ce_idx_end = self.output.index("\n", ce_idx_end) + 1
                # Get the information from the state line.
                trace_results = self._parse_trace_line(self.output[ce_idx:ce_idx_end])
                if trace_results:
                    _, file_name, line_number, method_name, _, _ = trace_results

                    if include_libs or Path(file_name).absolute().is_relative_to(
                        solution.base_dir.absolute()
                    ):
                        # Create Source file if not exists
                        if file_name not in solution.files_mapped:
                            solution.load_source_file(Path(file_name))

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
                if logger:
                    logger.debug(str(e))
                break
        return traces


class ESBMC(BaseSourceVerifier):
    """Verifier class that uses ESBMC."""

    def __init__(self) -> None:
        super().__init__(verifier_name="esbmc", authors="")

    @property
    def esbmc_path(self) -> Path:
        """Returns the ESBMC path from config."""
        return self.get_config_value("verifier.esbmc.path").absolute()

    @override
    def verify_source(
        self,
        *,
        solution: Solution,
        timeout: int | None = None,
        entry_function: str = "main",
        params: list[str] | None = None,
        **kwargs: Any,
    ) -> ESBMCOutput:
        _ = kwargs

        esbmc_params: list[str] = (
            params if params else self.get_config_value("verifier.esbmc.params")
        )

        if "--multi-property" in esbmc_params:
            self._logger.error(
                "Do not add --multi-property to ESBMC params it is not yet supported!",
            )
            sys.exit(1)

        if "--input-file" in esbmc_params:
            self._logger.error("Do not add --input-file to ESBMC parameters.")
            sys.exit(1)
        if "--timeout" in esbmc_params:
            self._logger.error(
                "Do not add --timeout to ESBMC parameters, instead specify it in its own field.",
            )
            sys.exit(1)
        if "--function" in esbmc_params:
            self._logger.error(
                "Don't add --function to ESBMC parameters, instead specify it in its own field.",
            )
            sys.exit(1)

        # Verify source is not responsible for saving the solution.
        assert solution.verify_solution_integrity(), (
            "Solution disk integrity check failed. There are unsaved changes. "
            "Save solution to a temporary location on disk."
        )

        # Check if cached version exists.
        enable_cache: bool = self.get_config_value("verifier.enable_cache")
        cache_properties: Any = [solution, entry_function, timeout, params, kwargs]
        if enable_cache:
            cached_result: Any = self._load_cached(cache_properties)
            if cached_result is not None:
                return cached_result

        # Call ESBMC to temporary folder.
        return_code, output = self._esbmc(
            solution=solution,
            esbmc_params=esbmc_params,
            entry_function=entry_function,
            timeout=timeout,
        )

        # Return
        result: ESBMCOutput = ESBMCOutput(
            return_code=return_code,
            output=output,
        )

        self.logger.debug(f"Verification Successful: {result.successful()}")
        self.logger.debug(f"ESBMC Exit Code: {return_code}")
        self.logger.debug(f"ESBMC Output: {output}")

        if enable_cache:
            self._save_cached(cache_properties, result)

        return result

    def _esbmc(
        self,
        solution: Solution,
        esbmc_params: list[str],
        entry_function: str,
        timeout: int | None = None,
    ) -> tuple[int, str]:
        """Exit code will be 0 if verification successful, 1 if verification
        failed. And any other number for compilation error/general errors."""

        # Build parameters list
        esbmc_cmd = [str(self.esbmc_path)]
        # ESBMC parameters
        esbmc_cmd.extend(esbmc_params)
        # Source code files (only accept valid ones)
        esbmc_cmd.append("--input-file")
        esbmc_cmd.extend(
            str(file.file_path) for file in solution.get_files_by_ext(["c", "cpp"])
        )
        # Header files/dir
        esbmc_cmd.extend("-I" + str(d) for d in solution.include_dirs.keys())

        # Add timeout suffix for parameter.
        if timeout:
            esbmc_cmd.extend(["--timeout", str(timeout) + "s"])
        # Add entry function for parameter.
        esbmc_cmd.extend(["--function", entry_function])

        self._logger.info("Running ESBMC: " + " ".join(esbmc_cmd))

        # Add slack time to process to allow verifier to timeout and end gracefully.
        process_timeout: float | None = timeout + 10 if timeout else None

        # Run ESBMC from solution base_dir and get output
        process: CompletedProcess = run(
            esbmc_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=solution.base_dir,
            timeout=process_timeout,
            check=False,
        )

        # Check segfault.
        if process.returncode == -signal.SIGSEGV:
            self._logger.error(
                "ESBMC has segfaulted... Please report the issue",
                "to developers: https://www.github.com/esbmc/esbmc",
            )
            sys.exit(1)

        output: str = process.stdout.decode("utf-8")
        return process.returncode, output
