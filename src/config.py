# Author: Yiannis Charalambous 2023

import os
import json
from dotenv import load_dotenv

from src.ai_models import *

openai_api_key: str = ""
esbmc_path: str = "./esbmc"
verbose: bool = False
raw_responses: bool = False
esbmc_params: list[str] = ["--z3", "--incremental-bmc"]
chat_temperature: float = 1.0
ai_model: str = "gpt-3.5-turbo"

cfg_sys_path: str = ""
cfg_sys_msg: dict

cfg_initial_prompt_path: str = ""
cfg_initial_prompt = []


def printv(m) -> None:
    if verbose:
        print(m)


def load_envs() -> None:
    load_dotenv()

    global openai_api_key
    openai_api_key = str(os.getenv("OPENAI_API_KEY"))

    global cfg_sys_path
    value = os.getenv("CFG_SYS_PATH")
    if value != None:
        if os.path.exists(value):
            cfg_sys_path = str(value)
        else:
            print(f"Error: Invalid .env CFG_SYS_PATH value: {value}")
            exit(4)

    global cfg_initial_prompt_path
    value = os.getenv("CFG_INITIAL_PROMPT_PATH")
    if value != None:
        if os.path.exists(value):
            cfg_initial_prompt_path = str(value)
        else:
            print(f"Error: Invalid .env CFG_INITIAL_PROMPT_PATH value: {value}")
            exit(4)

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
        if type(value) is str and is_valid_ai_model(str(value)):
            ai_model = str(value)
        else:
            print(f"Error: .env invalid AI_MODEL value: {ai_model}")
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


def init_ai_data() -> None:
    printv("Initializing AI data")
    # Will not be "" if valid. Checked already in load_envs()
    global cfg_sys_msg
    if cfg_sys_path != "":
        with open(cfg_sys_path, mode="r") as file:
            cfg_sys_msg = json.load(file)

    global cfg_initial_prompt
    if cfg_initial_prompt_path != "":
        with open(cfg_initial_prompt_path, mode="r") as file:
            cfg_initial_prompt = str(file.read())
