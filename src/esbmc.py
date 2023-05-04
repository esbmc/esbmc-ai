# Author: Yiannis Charalambous

import os
from subprocess import Popen, PIPE

import src.config as config


def esbmc(path: str, esbmc_params: list = config.esbmc_params):
    # Build parameters
    esbmc_cmd = [config.esbmc_path]
    esbmc_cmd.extend(esbmc_params)
    esbmc_cmd.append(path)

    # Run ESBMC and get output
    process = Popen(esbmc_cmd, stdout=PIPE)
    (output_bytes, err_bytes) = process.communicate()
    # Return
    exit_code = process.wait()
    output: str = str(output_bytes).replace("\\n", "\n")
    err: str = str(err_bytes).replace("\\n", "\n")
    return exit_code, output, err


def esbmc_load_source_code(
    source_code: str,
    esbmc_params: list = config.esbmc_params,
    auto_clean: bool = True,
):
    # Make temp folder
    if not os.path.exists("temp"):
        os.mkdir("temp")

    # Save to temporary folder.
    with open("temp/tempfile.c", "w") as file:
        file.write(source_code)

    # Call ESBMC to temporary folder.
    results = esbmc("temp/tempfile.c", esbmc_params)

    # Delete temporary file.
    if auto_clean:
        os.remove("temp/tempfile.c")

    # Return
    return results
