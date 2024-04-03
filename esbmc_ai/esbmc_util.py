# Author: Yiannis Charalambous

import os
import sys
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import Optional

from . import config


def esbmc_get_violated_property(esbmc_output: str) -> Optional[str]:
    """Gets the violated property line of the ESBMC output."""
    # Find "Violated property:" string in ESBMC output
    lines: list[str] = esbmc_output.splitlines()
    for ix, line in enumerate(lines):
        if "Violated property:" == line:
            return "\n".join(lines[ix : ix + 3])
    return None


def esbmc_get_counter_example(esbmc_output: str) -> Optional[str]:
    """Gets ESBMC output after and including [Counterexample]"""
    idx: int = esbmc_output.find("[Counterexample]\n")
    if idx == -1:
        return None
    else:
        return esbmc_output[idx:]


def esbmc_get_error_type(esbmc_output: str) -> str:
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


def get_source_code_err_line(esbmc_output: str) -> Optional[int]:
    # Find "Violated property:" string in ESBMC output
    violated_property: Optional[str] = esbmc_get_violated_property(esbmc_output)
    if violated_property:
        # Get the line of the violated property.
        pos_line: str = violated_property.splitlines()[1]
        pos_line_split: list[str] = pos_line.split(" ")
        for ix, word in enumerate(pos_line_split):
            if word == "line":
                # Get the line number
                return int(pos_line_split[ix + 1])
    return None


def get_source_code_err_line_idx(esbmc_output: str) -> Optional[int]:
    line: Optional[int] = get_source_code_err_line(esbmc_output)
    if line:
        return line - 1
    else:
        return None


def esbmc(path: str, esbmc_params: list, timeout: Optional[float] = None):
    """Exit code will be 0 if verification successful, 1 if verification
    failed. And any other number for compilation error/general errors."""
    # Build parameters
    esbmc_cmd = [config.esbmc_path]
    esbmc_cmd.extend(esbmc_params)
    esbmc_cmd.append(path)

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


def esbmc_load_source_code(
    file_path: str,
    source_code: str,
    esbmc_params: list = config.esbmc_params,
    auto_clean: bool = config.temp_auto_clean,
    timeout: Optional[float] = None,
):
    source_code_path = Path(file_path)

    # Create temp path.
    delete_path: bool = False
    if not os.path.exists(config.temp_file_dir):
        os.mkdir(config.temp_file_dir)
        delete_path = True

    temp_file_path = f"{config.temp_file_dir}{os.sep}{source_code_path.name}"

    # Create temp file.
    with open(temp_file_path, "w") as file:
        # Save to temporary folder and flush contents.
        file.write(source_code)
        file.flush()

        # Call ESBMC to temporary folder.
        results = esbmc(file.name, esbmc_params, timeout=timeout)

    # Delete temp files and path
    if auto_clean:
        # Remove file
        os.remove(temp_file_path)
        # Remove file path if created this run and is empty.
        if delete_path and len(os.listdir(config.temp_file_dir)) == 0:
            os.rmdir(config.temp_file_dir)

    # Return
    return results
