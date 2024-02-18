# Author: Yiannis Charalambous

import os
import re
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path

from . import config


def esbmc(path: str, esbmc_params: list):
    """Exit code will be 0 if verification successful, 1 if verification
    failed. And any other number for compilation error/general errors."""
    # Build parameters
    esbmc_cmd = [config.esbmc_path]
    esbmc_cmd.extend(esbmc_params)
    esbmc_cmd.append(path)

    # Run ESBMC and get output
    process = Popen(esbmc_cmd, stdout=PIPE, stderr=STDOUT)
    (output_bytes, err_bytes) = process.communicate()
    # Return
    exit_code = process.wait()
    output: str = str(output_bytes).replace("\\n", "\n")
    err: str = str(err_bytes).replace("\\n", "\n")
    output = esbmc_output_optimisation(output)
    return exit_code, output, err

def esbmc_output_optimisation(esbmc_output:str) -> str:

    esbmc_output =re.sub(r'^\d+. The output mentions that no solver was specified, so ESBMC defaults to using the Boolector solver\.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'^\d+. This output states that the solving process with the Boolector solver took a certain amount of time\.','', esbmc_output, flags=re.MULTILINE)  
    esbmc_output = re.sub(r'[-]+', '', esbmc_output)  # Remove lines of dashes
    esbmc_output = re.sub(r'\b[0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8}\b', '', esbmc_output)  # Remove hex patterns
    esbmc_output = re.sub(r'^Line \d+: ESBMC is using the Boolector solver \d+\.\d+\.\d+ to solve the encoding\.$', '', esbmc_output, flags=re.MULTILINE)  # Remove Boolector lines
    esbmc_output = re.sub(r'\d+. ESBMC is using the Boolector solver \d+\. \d+\. \d+ to solve the encoding\.$', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'^Line \d+: The solver takes \d+\.\d+s to determine the runtime decision procedure\.$', '', esbmc_output, flags=re.MULTILINE)  # Remove solver time lines
    esbmc_output = re.sub(r'.*Boolector.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output =re.sub(r'/\*.*?\*/', '', esbmc_output, flags=re.MULTILINE)
    pattern = r"- `.*Slicing time: \d+\.\d+s \(removed \d+ assignments\)`.*: ESBMC has performed slicing, a technique that removes irrelevant assignments from the program and reduces the complexity of analysis."
    esbmc_output = re.sub(pattern, '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\n\*s\n', '\n', esbmc_output)
    esbmc_output = esbmc_output.replace("output from ESBMC", "ESBMC output")

    return esbmc_output


def esbmc_load_source_code(
    file_path: str,
    source_code: str,
    esbmc_params: list = config.esbmc_params,
    auto_clean: bool = config.temp_auto_clean,
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
        results = esbmc(file.name, esbmc_params)

    # Delete temp files and path
    if auto_clean:
        # Remove file
        os.remove(temp_file_path)
        # Remove file path if created this run and is empty.
        if delete_path and len(os.listdir(config.temp_file_dir)) == 0:
            os.rmdir(config.temp_file_dir)

    # Return
    return results
