# Author: Yiannis Charalambous 2023

import os
from dotenv import load_dotenv

openai_api_key: str = ""
verbose: bool = False
raw_responses: bool = False
esbmc_params: list[str] = ["--z3", "--unwind", "5"]


def load_args(args) -> None:
    global verbose
    verbose = args.verbose

    global raw_responses
    raw_responses = args.raw_output

    global esbmc_params
    if len(args.remaining) != 0:
        esbmc_params = args.remaining


def load_envs() -> None:
    global openai_api_key

    load_dotenv()

    openai_api_key = str(os.getenv("OPENAI_API_KEY"))
