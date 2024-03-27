# Author: Yiannis Charalambous

import os
import sys
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import Optional

from . import config


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
    process_timeout: Optional[float] = timeout + 1 if timeout else None

    # Run ESBMC and get output
    process: CompletedProcess = run(
        esbmc_cmd,
        stdout=PIPE,
        stderr=STDOUT,
        timeout=process_timeout,
    )

    output_bytes: bytes = process.stdout
    err_bytes: bytes = process.stderr
    output: str = str(output_bytes).replace("\\n", "\n")
    err: str = str(err_bytes).replace("\\n", "\n")

    return process.returncode, output, err


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
