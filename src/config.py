# Author: Yiannis Charalambous 2023

import os
from dotenv import load_dotenv

openai_api_key: str = ""
esbmc_path: str = "./esbmc"
verbose: bool = False
raw_responses: bool = False
esbmc_params: list[str] = ["--z3", "--incremental-bmc"]
chat_temperature: float = 1.0
ai_model: str = "gpt-3.5-turbo"


def load_envs() -> None:
    load_dotenv()

    global openai_api_key
    openai_api_key = str(os.getenv("OPENAI_API_KEY"))

    global chat_temperature
    chat_temperature = float(str(os.getenv("CHAT_TEMPERATURE")))

    global ai_model
    ai_model = str(os.getenv("AI_MODEL"))

    global esbmc_path
    value = os.getenv("ESBMC_PATH")
    if value != None and value != "":
        esbmc_path = str(value)


def load_args(args) -> None:
    global verbose
    verbose = args.verbose

    global raw_responses
    raw_responses = args.raw_output

    global ai_model
    if args.ai_model != "":
        ai_model = args.ai_model

    global esbmc_params
    if len(args.remaining) != 0:
        esbmc_params = args.remaining
