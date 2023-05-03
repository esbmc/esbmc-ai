# Author: Yiannis Charalambous 2023

import os
import json
from dotenv import load_dotenv

from src.ai_models import *

verbose: bool = False
openai_api_key: str = ""
raw_responses: bool = False

esbmc_path: str = "./esbmc"
esbmc_params: list[str] = [
    "--interval-analysis",
    "--goto-unwind",
    "--unlimited-goto-unwind",
    "--k-induction",
    "--state-hashing",
    "--add-symex-value-sets",
    "--k-step",
    "2",
    "--floatbv",
    "--unlimited-k-steps",
]

chat_temperature: float = 1.0
ai_model: str = "gpt-3.5-turbo"

cfg_path: str = "./config.json"

cfg_sys_msg: dict
cfg_initial_prompt = []


def printv(m) -> None:
    if verbose:
        print(m)


def load_envs() -> None:
    load_dotenv(dotenv_path="./.env", override=True, verbose=True)

    global openai_api_key
    openai_api_key = str(os.getenv("OPENAI_API_KEY"))

    global cfg_path
    value = os.getenv("ESBMC_AI_CFG_PATH")
    if value != None:
        if os.path.exists(value):
            cfg_path = str(value)
        else:
            print(f"Error: Invalid .env ESBMC_AI_CFG_PATH value: {value}")
            exit(4)
    else:
        print(
            f"Warning: ESBMC_AI_CFG_PATH not found in .env file... Defaulting to {cfg_path}"
        )


def load_config(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"Error: Config not found: {file_path}")
        exit(4)

    config_file = None
    with open(file_path, mode="r") as file:
        config_file = json.load(file)

    global chat_temperature
    if "chat_temperature" in config_file:
        if (
            type(config_file["chat_temperature"]) is float
            or type(config_file["chat_temperature"]) is int
        ):
            chat_temperature = config_file["chat_temperature"]
        else:
            print(
                f"Error: Invalid .env CHAT_TEMPERATURE value: {config_file['chat_temperature']}"
            )
            print("Make sure it is a float or int...")
            exit(4)
    else:
        print(
            f"Warning: CHAT_TEMPERATURE not found in .env file... Defaulting to {chat_temperature}"
        )

    global ai_model
    if "ai_model" in config_file:
        value = config_file["ai_model"]
        if type(value) is str and is_valid_ai_model(value):
            ai_model = value
        else:
            print(f"Error: .env invalid AI_MODEL value: {ai_model}")
            exit(4)
    else:
        print(f"Warning: AI_MODEL not found in .env file... Defaulting to {ai_model}")

    global esbmc_path
    # Health check verifies this.
    if "esbmc_path" in config_file and config_file["esbmc_path"] != "":
        esbmc_path = config_file["esbmc_path"]

    printv("Initializing AI data")
    # Will not be "" if valid. Checked already in load_envs()
    global cfg_sys_msg
    cfg_sys_msg = config_file["prompts"]["system"]

    global cfg_initial_prompt
    cfg_initial_prompt = config_file["prompts"]["initial"]


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
