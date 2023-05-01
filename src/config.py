# Author: Yiannis Charalambous 2023

import os
from dotenv import load_dotenv

from ai_models import *

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
    value = os.getenv("CHAT_TEMPERATURE")
    if value != None:
        try:
            chat_temperature = float(str(value))
        except ValueError:
            print(f"Error: Invalid .env CHAT_TEMPERATURE value: {value}")
            exit(4)
    else:
        print(
            f"Warning: CHAT_TEMPERATURE not found in .env file... Defaulting to {chat_temperature}"
        )

    global ai_model
    value = os.getenv("AI_MODEL")
    if value != None:
        if value is str and is_valid_ai_model(str(value)):
            ai_model = str(value)
        else:
            print(f"Error: .env invalid AI_MODEL value, defaulting to {ai_model}")
            exit(4)
    else:
        print(f"Warning: AI_MODEL not found in .env file... Defaulting to {ai_model}")

    global esbmc_path
    # Health check verifies this.
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
        if is_valid_ai_model(args.ai_model):
            ai_model = args.ai_model
        else:
            print(f"Error: invalid --ai-model parameter {args.ai_model}")
            exit(4)

    global esbmc_params
    if len(args.remaining) != 0:
        esbmc_params = args.remaining
