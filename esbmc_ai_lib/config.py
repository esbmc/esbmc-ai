# Author: Yiannis Charalambous 2023

import os
import json
from typing import Any, NamedTuple, Union
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
    "--compact-trace",
]

temp_auto_clean: bool = True
temp_file_dir: str = "."
consecutive_prompt_delay: float = 20.0
ai_model: AIModel = AI_MODEL_GPT3

cfg_path: str = "./config.json"


class ChatPromptSettings(NamedTuple):
    system_messages: list
    initial_prompt: str
    temperature: float


chat_prompt_user_mode: ChatPromptSettings
chat_prompt_generator_mode: ChatPromptSettings
chat_prompt_conversation_summarizer: ChatPromptSettings


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


def _load_config_value(
    config_file: dict, name: str, default: object = None
) -> tuple[Any, bool]:
    if name in config_file:
        return config_file[name], True
    else:
        print(f"Warning: {name} not found in config... Using default value: {default}")
        return default, False


def _load_config_real_number(
    config_file: dict, name: str, default: object = None
) -> Union[int, float]:
    value, _ = _load_config_value(config_file, name, default)
    # Type check
    if type(value) is float or type(value) is int:
        return value
    else:
        raise TypeError(
            f"Error: config invalid {name} value: {value} "
            + "Make sure it is a float or int..."
        )


def load_config(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"Error: Config not found: {file_path}")
        exit(4)

    config_file = None
    with open(file_path, mode="r") as file:
        config_file = json.load(file)

    global esbmc_params
    esbmc_params, _ = _load_config_value(
        config_file,
        "esbmc_params",
        esbmc_params,
    )

    global consecutive_prompt_delay
    consecutive_prompt_delay = _load_config_real_number(
        config_file,
        "consecutive_prompt_delay",
        consecutive_prompt_delay,
    )

    global temp_auto_clean
    temp_auto_clean, _ = _load_config_value(
        config_file,
        "temp_auto_clean",
        temp_auto_clean,
    )

    global temp_file_dir
    temp_file_dir, _ = _load_config_value(
        config_file,
        "temp_file_dir",
        temp_file_dir,
    )

    global ai_model
    ai_model_name, _ = _load_config_value(
        config_file,
        "ai_model",
        ai_model,
    )
    if not is_valid_ai_model(ai_model_name):
        print(f"Error: {ai_model_name} is not a valid AI model")
        exit(4)
    else:
        for model in models:
            if ai_model_name == model.name:
                ai_model = model

    global esbmc_path
    # Health check verifies this later in the init process.
    esbmc_path, _ = _load_config_value(
        config_file,
        "esbmc_path",
        esbmc_path,
    )

    # Load the AI data from the file that will command the AI for all modes.
    printv("Initializing AI data")
    # TODO Add checking here.
    global chat_prompt_user_mode
    chat_prompt_user_mode = ChatPromptSettings(
        system_messages=config_file["chat_modes"]["user_chat"]["system"],
        initial_prompt=config_file["chat_modes"]["user_chat"]["initial"],
        temperature=config_file["chat_modes"]["user_chat"]["temperature"],
    )

    global chat_prompt_generator_mode
    chat_prompt_generator_mode = ChatPromptSettings(
        system_messages=config_file["chat_modes"]["generate_solution"]["system"],
        initial_prompt=config_file["chat_modes"]["generate_solution"]["initial"],
        temperature=config_file["chat_modes"]["generate_solution"]["temperature"],
    )

    global chat_prompt_conversation_summarizer
    chat_prompt_conversation_summarizer = ChatPromptSettings(
        system_messages=config_file["chat_modes"]["conv_summarizer"]["system"],
        initial_prompt=config_file["chat_modes"]["conv_summarizer"]["initial"],
        temperature=config_file["chat_modes"]["conv_summarizer"]["temperature"],
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
