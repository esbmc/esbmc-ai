# Author: Yiannis Charalambous 2023

import importlib
from importlib.util import find_spec
from importlib.machinery import ModuleSpec
import os
import sys
from platform import system as system_name
from pathlib import Path
import tomllib as toml
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from dotenv import load_dotenv, find_dotenv
from langchain.schema import HumanMessage

from esbmc_ai.config_field import ConfigField
from esbmc_ai.chat_response import list_to_base_messages
from esbmc_ai.logging import printv, set_verbose
from .ai_models import (
    BaseMessage,
    is_valid_ai_model,
    get_ai_model_by_name,
    add_custom_ai_model,
    AIModel,
    OllamaAIModel,
)
from .api_key_collection import APIKeyCollection

FixCodeScenarios = dict[str, dict[str, str | tuple[BaseMessage, ...]]]
"""Type for scenarios. A single scenario contains initial and system components.

* Initial message can be accessed like so: `x["base"]["initial"]`
* System messages can be accessed like so: `x["base"]["system"]`

The config loader ensures they conform to the specifications."""

default_scenario: str = "base"


def _validate_prompt_template_conversation(prompt_template: List[Dict]) -> bool:
    """Used to validate if a prompt template conversation is of the correct format
    in the config before loading it."""

    for msg in prompt_template:
        if (
            not isinstance(msg, dict)
            or "content" not in msg
            or "role" not in msg
            or not isinstance(msg["content"], str)
            or not isinstance(msg["role"], str)
        ):
            return False
    return True


def _validate_prompt_template(conv: Dict[str, List[Dict]]) -> bool:
    """Used to check if a prompt template (contains conversation and initial message) is
    of the correct format."""
    if (
        "initial" not in conv
        or not isinstance(conv["initial"], str)
        or "system" not in conv
        or not _validate_prompt_template_conversation(conv["system"])
    ):
        return False
    return True


def _validate_addon_modules(mods: list[str]) -> bool:
    """Validates that all values are string."""
    for m in mods:
        if not isinstance(m, str):
            return False
        spec: Optional[ModuleSpec] = find_spec(m)
        if spec is None:
            return False
    return True


def _init_addon_modules(mods: list[str]) -> list:
    """Will import addon modules that exist and iterate through the exposed
    attributes, will then get all available exposed classes and store them.

    This method will load:
    * ChatCommands
    * BaseSourceVerifier classes"""
    from esbmc_ai.commands.chat_command import ChatCommand
    from esbmc_ai.verifiers import BaseSourceVerifier

    allowed_types = ChatCommand | BaseSourceVerifier

    result: list = []
    for module_name in mods:
        try:
            m = importlib.import_module(module_name)
            for attr_name in getattr(m, "__all__"):
                # Get the class
                attr_class = getattr(m, attr_name)
                # Check if valid addon type and import
                if issubclass(attr_class, allowed_types):
                    result.append(attr_class())
                    printv(f"Loading addon: {attr_name}")
        except ModuleNotFoundError as e:
            print(f"Addon Loader: Could not import module: {module_name}: {e}")
            sys.exit(1)

    return result


class Config:
    """Config loader for ESBMC-AI"""

    api_keys: APIKeyCollection
    raw_conversation: bool = False
    cfg_path: Path
    generate_patches: bool
    output_dir: Optional[Path] = None

    _fields: List[ConfigField] = [
        ConfigField(
            name="ai_model",
            default_value=None,
            # Api keys are loaded from system env so they are already
            # available
            validate=lambda v: isinstance(v, str)
            and is_valid_ai_model(v, Config.api_keys),
            on_load=lambda v: get_ai_model_by_name(v, Config.api_keys),
        ),
        ConfigField(
            name="temp_auto_clean",
            default_value=True,
            validate=lambda v: isinstance(v, bool),
        ),
        ConfigField(
            name="temp_file_dir",
            default_value=None,
            validate=lambda v: isinstance(v, str) and Path(v).is_file(),
            on_load=Path,
            default_value_none=True,
        ),
        ConfigField(
            name="allow_successful",
            default_value=False,
            validate=lambda v: isinstance(v, bool),
        ),
        ConfigField(
            name="loading_hints",
            default_value=True,
            validate=lambda v: isinstance(v, bool),
        ),
        ConfigField(
            name="source_code_format",
            default_value="full",
            validate=lambda v: isinstance(v, str) and v in ["full", "single"],
            error_message="source_code_format can only be 'full' or 'single'",
        ),
        # Store as a list of commands
        ConfigField(
            name="addon_modules",
            default_value=[],
            validate=_validate_addon_modules,
            on_load=_init_addon_modules,
            error_message="addon_modules must be a list of Python modules to load",
        ),
        ConfigField(
            name="esbmc.path",
            default_value=None,
            validate=lambda v: isinstance(v, str) and Path(v).expanduser().is_file(),
            on_load=lambda v: Path(v).expanduser(),
        ),
        ConfigField(
            name="esbmc.params",
            default_value=[
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
                "--context-bound",
                "2",
            ],
            validate=lambda v: isinstance(v, list),
        ),
        ConfigField(
            name="esbmc.output_type",
            default_value="full",
            validate=lambda v: v in ["full", "vp", "ce"],
        ),
        ConfigField(
            name="esbmc.timeout",
            default_value=60,
            validate=lambda v: isinstance(v, int),
        ),
        ConfigField(
            name="llm_requests.max_tries",
            default_value=5,
            validate=lambda v: isinstance(v, int),
        ),
        ConfigField(
            name="llm_requests.timeout",
            default_value=60,
            validate=lambda v: isinstance(v, int),
        ),
        ConfigField(
            name="user_chat.temperature",
            default_value=1.0,
            validate=lambda v: isinstance(v, float) and 0 <= v <= 2.0,
            error_message="Temperature needs to be a value between 0 and 2.0",
        ),
        ConfigField(
            name="fix_code.temperature",
            default_value=1.0,
            validate=lambda v: isinstance(v, float) and 0 <= v <= 2,
            error_message="Temperature needs to be a value between 0 and 2.0",
        ),
        ConfigField(
            name="fix_code.max_attempts",
            default_value=5,
            validate=lambda v: isinstance(v, int),
        ),
        ConfigField(
            name="fix_code.message_history",
            default_value="normal",
            validate=lambda v: v in ["normal", "latest_only", "reverse"],
            error_message='fix_code.message_history can only be "normal", "latest_only", "reverse"',
        ),
        ConfigField(
            name="prompt_templates.user_chat.initial",
            default_value=None,
            validate=lambda v: isinstance(v, str),
            on_load=lambda v: HumanMessage(content=v),
        ),
        ConfigField(
            name="prompt_templates.user_chat.system",
            default_value=None,
            validate=_validate_prompt_template_conversation,
            on_load=list_to_base_messages,
        ),
        ConfigField(
            name="prompt_templates.user_chat.set_solution",
            default_value=None,
            validate=_validate_prompt_template_conversation,
            on_load=list_to_base_messages,
        ),
        # Here we have a list of prompt templates that are for each scenario.
        # The base scenario prompt template is required.
        ConfigField(
            name="prompt_templates.fix_code",
            default_value=None,
            validate=lambda v: default_scenario in v
            and all(
                _validate_prompt_template(prompt_template)
                for prompt_template in v.values()
            ),
            on_read=lambda config_file: {
                scenario: {
                    "initial": HumanMessage(content=conv["initial"]),
                    "system": list_to_base_messages(conv["system"]),
                }
                for scenario, conv in config_file["prompt_templates"][
                    "fix_code"
                ].items()
            },
        ),
    ]
    _values: Dict[str, Any] = {}

    # Define some shortcuts for the values here (instead of having to use get_value)

    @classmethod
    def get_ai_model(cls) -> AIModel:
        """Value of field: ai_model"""
        return cls.get_value("ai_model")

    @classmethod
    def get_llm_requests_max_tries(cls) -> int:
        """Value of field: llm_requests.max_tries"""
        return cls.get_value("llm_requests.max_tries")

    @classmethod
    def get_llm_requests_timeout(cls) -> float:
        """"""
        return cls.get_value("llm_requests.timeout")

    @classmethod
    def get_user_chat_initial(cls) -> BaseMessage:
        """Value of field: prompt_templates.user_chat.initial"""
        return cls.get_value("prompt_templates.user_chat.initial")

    @classmethod
    def get_user_chat_system_messages(cls) -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.system"""
        return cls.get_value("prompt_templates.user_chat.system")

    @classmethod
    def get_user_chat_set_solution(cls) -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.set_solution"""
        return cls.get_value("prompt_templates.user_chat.set_solution")

    @classmethod
    def get_fix_code_scenarios(cls) -> FixCodeScenarios:
        """Value of field: prompt_templates.fix_code"""
        return cls.get_value("prompt_templates.fix_code")

    @classmethod
    def init(cls, args: Any) -> None:
        """Static init method for the static class. Will load the config from
        the args, the env file and then from config file."""
        cls._load_envs()

        if not Config.cfg_path.exists() and Config.cfg_path.is_file():
            print(f"Error: Config not found: {Config.cfg_path}")
            sys.exit(1)

        with open(Config.cfg_path, "r") as file:
            cls.original_config_file: dict[str, Any] = toml.loads(file.read())

        # Load custom AIs
        if "ai_custom" in cls.original_config_file:
            _load_custom_ai(cls.original_config_file["ai_custom"])

        # Flatten dict as the _fields are defined in a flattened format for
        # convenience.
        cls.config_file: dict[str, Any] = cls._flatten_dict(cls.original_config_file)

        # Load all the config file field entries
        for field in cls._fields:
            cls.add_config_field(field)

        cls._load_args(args)

    @classmethod
    def add_config_field(cls, field: ConfigField) -> None:
        """Loads a new field from the config. Init needs to be called before
        calling this to initialize the base config."""
        # If on_read is overwritten, then the reading process is manually
        # defined so fallback to that.
        if field.on_read:
            cls._values[field.name] = field.on_read(cls.original_config_file)
            return

        # Proceed to default read

        # Is field entry found in config?
        if field.name in cls.config_file:
            # Check if None and not allowed!
            if (
                field.default_value is None
                and not field.default_value_none
                and cls.config_file[field.name] is None
            ):
                raise ValueError(
                    f"The config entry {field.name} has a None value when it can't be"
                )

            # Validate field
            assert field.validate(cls.config_file[field.name]), (
                field.error_message
                if field.error_message
                else f"Field: {field.name} is invalid: {cls.config_file[field.name]}"
            )

            # Assign field from config file
            cls._values[field.name] = field.on_load(cls.config_file[field.name])
        elif field.default_value is None and not field.default_value_none:
            raise KeyError(f"{field.name} is missing from config file")
        else:
            # Use default value
            cls._values[field.name] = field.default_value

    @classmethod
    def get_value(cls, name: str) -> Any:
        """Gets the value of key name"""
        return cls._values[name]

    @classmethod
    def set_value(cls, name: str, value: Any) -> None:
        """Sets a value in the config, if it does not exist, it will create one.
        This uses toml notation dot notation to namespace the elements."""
        cls._values[name] = value

    @classmethod
    def _load_envs(cls) -> None:
        """Environment variables are loaded in the following order:

        1. Environment variables already loaded. Any variable not present will be looked for in
        .env files in the following locations.
        2. .env file in the current directory, moving upwards in the directory tree.
        3. esbmc-ai.env file in the current directory, moving upwards in the directory tree.
        4. esbmc-ai.env file in $HOME/.config/ for Linux/macOS and %userprofile% for Windows.

        Note: ESBMCAI_CONFIG_PATH undergoes tilde user expansion and also environment
        variable expansion.
        """

        def get_env_vars() -> None:
            """Gets all the system environment variables that are currently loaded."""
            for k in keys:
                value: Optional[str] = os.getenv(k)
                if value is not None:
                    values[k] = value

        keys: list[str] = ["OPENAI_API_KEY", "ESBMCAI_CONFIG_PATH"]
        values: dict[str, str] = {}

        # Load from system env
        get_env_vars()

        # Find .env in current working directory and load it.
        dotenv_file_path: str = find_dotenv(usecwd=True)
        if dotenv_file_path != "":
            load_dotenv(dotenv_path=dotenv_file_path, override=False, verbose=True)
        else:
            # Find esbmc-ai.env in current working directory and load it.
            dotenv_file_path: str = find_dotenv(filename="esbmc-ai.env", usecwd=True)
            if dotenv_file_path != "":
                load_dotenv(dotenv_path=dotenv_file_path, override=False, verbose=True)

        get_env_vars()

        # Look for .env in home folder.
        home_path: Path = Path.home()
        match system_name():
            case "Linux" | "Darwin":
                home_path /= ".config/esbmc-ai.env"
            case "Windows":
                home_path /= "esbmc-ai.env"
            case _:
                raise ValueError(f"Unknown OS type: {system_name()}")

        load_dotenv(home_path, override=False, verbose=True)

        get_env_vars()

        # Check if all the values are set, else error.
        for key in keys:
            if key not in values:
                print(f"Error: No ${key} in environment.")
                sys.exit(1)

        cls.api_keys = APIKeyCollection(
            openai=str(os.getenv("OPENAI_API_KEY")),
        )

        cls.cfg_path = Path(
            os.path.expanduser(
                os.path.expandvars(str(os.getenv("ESBMCAI_CONFIG_PATH")))
            )
        )

    @classmethod
    def _load_args(cls, args) -> None:
        set_verbose(args.verbose)

        # AI Model -m
        if args.ai_model != "":
            if is_valid_ai_model(args.ai_model, cls.api_keys):
                ai_model = get_ai_model_by_name(args.ai_model, cls.api_keys)
                cls.set_value("ai_model", ai_model)
            else:
                print(f"Error: invalid --ai-model parameter {args.ai_model}")
                sys.exit(4)

        # If append flag is set, then append.
        if args.append:
            esbmc_params: List[str] = cls.get_value("esbmc.params")
            esbmc_params.extend(args.remaining)
            cls.set_value("esbmc_params", esbmc_params)
        elif len(args.remaining) != 0:
            cls.set_value("esbmc_params", args.remaining)

        Config.raw_conversation = args.raw_conversation
        Config.generate_patches = args.generate_patches

        if args.output_dir:
            path: Path = Path(args.output_dir).expanduser()
            if path.is_dir():
                Config.output_dir = path
            else:
                print(
                    "Error while parsing arguments: output_dir: dir does not exist:",
                    Config.output_dir,
                )
                sys.exit(1)

    @classmethod
    def _flatten_dict(cls, d, parent_key="", sep="."):
        """Recursively flattens a nested dictionary."""
        items = {}
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, dict):
                items.update(cls._flatten_dict(v, new_key, sep=sep))
            else:
                items[new_key] = v
        return items


def _load_custom_ai(config: dict) -> None:
    """Loads custom AI defined in the config and ascociates it with the AIModels
    module."""

    def _load_config_value(
        config_file: dict, name: str, default: object = None
    ) -> tuple[Any, bool]:
        if name in config_file:
            return config_file[name], True

        print(f"Warning: {name} not found in config... Using default value: {default}")
        return default, False

    for name, ai_data in config.items():
        # Load the max tokens
        custom_ai_max_tokens, ok = _load_config_value(
            config_file=ai_data,
            name="max_tokens",
        )
        assert ok, f'max_tokens field not found in "ai_custom" entry "{name}".'
        assert (
            isinstance(custom_ai_max_tokens, int) and custom_ai_max_tokens > 0
        ), f'custom_ai_max_tokens in ai_custom entry "{name}" needs to be an int and greater than 0.'

        # Load the URL
        custom_ai_url, ok = _load_config_value(
            config_file=ai_data,
            name="url",
        )
        assert ok, f'url field not found in "ai_custom" entry "{name}".'

        # Get provider type
        server_type, ok = _load_config_value(
            config_file=ai_data,
            name="server_type",
            default="localhost:11434",
        )
        assert (
            ok
        ), f"server_type for custom AI '{name}' is invalid, it needs to be a valid string"

        # Create correct type of LLM
        llm: AIModel
        match server_type:
            case "ollama":
                llm = OllamaAIModel(
                    name=name,
                    tokens=custom_ai_max_tokens,
                    url=custom_ai_url,
                )
            case _:
                raise NotImplementedError(
                    f"The custom AI server type is not implemented: {server_type}"
                )

        # Add the custom AI.
        add_custom_ai_model(llm)
