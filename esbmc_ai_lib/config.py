# Author: Yiannis Charalambous 2023

import os
import json
from typing import Any, Union
from dotenv import load_dotenv

from .logging import *
from .ai_models import *

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

consecutive_prompt_delay: float = 20.0
chat_temperature: float = 1.0
code_fix_temperature: float = 1.1
ai_model: str = AI_MODEL_GPT3

cfg_path: str = "./config.json"


class ChatPromptSettings(object):
    system_messages: list
    initial_prompt: str

    def __init__(self, system_messages: list, initial_prompt: str) -> None:
        super().__init__()
        self.system_messages = system_messages
        self.initial_prompt = initial_prompt


chat_prompt_user_mode: ChatPromptSettings
chat_prompt_generator_mode: ChatPromptSettings


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


def _load_config_value(config_file: dict, name: str, default: object = None) -> Any:
    if name in config_file:
        return config_file[name], True
    else:
        print(f"Warning: {name} not found in config... Using default value: {default}")
        return default, False


def _load_config_real_number(config_file: dict, name: str, default: object = None) -> Union[int, float]:
    value, _ = _load_config_value(config_file, name, default)
    # Type check
    if type(value) is float or type(value) is int:
        return value
    else:
        print(f"Error: config invalid {name} value: {value}")
        print("Make sure it is a float or int...")
        exit(4)


def load_config(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"Error: Config not found: {file_path}")
        exit(4)

    config_file = None
    with open(file_path, mode="r") as file:
        config_file = json.load(file)

    global esbmc_params
    if "esbmc_params" in config_file:
        esbmc_params = config_file["esbmc_params"]
    else:
        print(
            f"Warning: esbmc_params not found in config... Defaulting to {esbmc_params}"
        )

    global consecutive_prompt_delay
    consecutive_prompt_delay = _load_config_real_number(
        config_file,
        "consecutive_prompt_delay",
        consecutive_prompt_delay,
    )

    global chat_temperature
    chat_temperature = _load_config_real_number(
        config_file,
        "chat_temperature",
        chat_temperature,
    )

    global code_fix_temperature
    code_fix_temperature = _load_config_real_number(
        config_file,
        "code_fix_temperature",
        code_fix_temperature,
    )

    global ai_model
    ai_model, _ = _load_config_value(
        config_file,
        "ai_model",
        ai_model,
    )
    if not is_valid_ai_model(ai_model):
        print(f"Error: {ai_model} is not a valid AI model")
        exit(4)
    
    global esbmc_path
    # Health check verifies this.
    if "esbmc_path" in config_file and config_file["esbmc_path"] != "":
        esbmc_path = config_file["esbmc_path"]

    # Load the AI data from the file that will command the AI for all modes.
    printv("Initializing AI data")
    # TODO Add checking here.
    global chat_prompt_user_mode
    chat_prompt_user_mode = ChatPromptSettings(
        system_messages=config_file["prompts"]["user_mode"]["system"],
        initial_prompt=config_file["prompts"]["user_mode"]["initial"],
    )

    global chat_prompt_generator_mode
    chat_prompt_generator_mode = ChatPromptSettings(
        system_messages=config_file["prompts"]["generate_solution"]["system"],
        initial_prompt=config_file["prompts"]["generate_solution"]["initial"],
    )


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
    # If append flag is set, then append.
    if args.append:
        esbmc_params.extend(args.remaining)
    elif len(args.remaining) != 0:
        esbmc_params = args.remaining
