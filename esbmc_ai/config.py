# Author: Yiannis Charalambous 2023


import argparse
from dataclasses import dataclass
import os
import sys
from platform import system as system_name
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)

from dotenv import load_dotenv, find_dotenv
from langchain.schema import HumanMessage, BaseMessage

from esbmc_ai.config_field import ConfigField
from esbmc_ai.base_config import BaseConfig, default_scenario
from esbmc_ai.chat_response import list_to_base_messages
from esbmc_ai.logging import set_verbose
from esbmc_ai.ai_models import (
    AIModel,
    AIModels,
    OllamaAIModel,
)


@dataclass
class FixCodeScenario:
    """Type for scenarios. A single scenario contains initial and system components."""

    initial: BaseMessage
    system: tuple[BaseMessage, ...]


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


class Config(BaseConfig):
    """Config loader for ESBMC-AI"""

    _instance: "Config | None" = None
    _initialized: bool = False
    _args: argparse.Namespace
    raw_conversation: bool = False
    generate_patches: bool
    output_dir: Path | None = None

    def __new__(cls):
        if cls._instance:
            return cls._instance

        cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if Config._initialized:
            return

        Config._initialized = True
        super().__init__()

    # Define some shortcuts for the values here (instead of having to use get_value)

    def get_ai_model(self) -> AIModel:
        """Value of field: ai_model"""
        return self.get_value("ai_model")

    def get_llm_requests_max_tries(self) -> int:
        """Value of field: llm_requests.max_tries"""
        return self.get_value("llm_requests.max_tries")

    def get_llm_requests_timeout(self) -> float:
        """Max timeout for a request when prompting the LLM"""
        return self.get_value("llm_requests.timeout")

    def get_user_chat_initial(self) -> BaseMessage:
        """Value of field: prompt_templates.user_chat.initial"""
        return self.get_value("prompt_templates.user_chat.initial")

    def get_user_chat_system_messages(self) -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.system"""
        return self.get_value("prompt_templates.user_chat.system")

    def get_user_chat_set_solution(self) -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.set_solution"""
        return self.get_value("prompt_templates.user_chat.set_solution")

    def get_fix_code_scenarios(self) -> dict[str, FixCodeScenario]:
        """Value of field: prompt_templates.fix_code"""
        return self.get_value("prompt_templates.fix_code")

    @property
    def filenames(self) -> list[Path]:
        """Gets the filanames that are to be loaded"""
        return self.get_value("solution.filenames")

    @classmethod
    def init(cls, args: Any) -> None:
        """Will load the config from the args, the env file and then from config file.
        Call once to initialize."""

        config: Config = Config()
        config._args = args

        # Huggingface warning supress
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        config._load_envs(
            ConfigField.from_env(
                name="ESBMCAI_CONFIG_FILE",
                default_value=None,
                on_load=lambda v: Path(os.path.expanduser(os.path.expandvars(str(v)))),
            ),
            ConfigField.from_env(
                name="OPENAI_API_KEY",
                default_value=None,
                default_value_none=True,
            ),
            ConfigField.from_env(
                name="ANTHROPIC_API_KEY",
                default_value=None,
                default_value_none=True,
            ),
        )

        config.set_custom_field(
            ConfigField(
                name="api_keys",
                default_value={},
            ),
            value={
                "openai": config.get_value("OPENAI_API_KEY"),
                "anthropic": config.get_value("ANTHROPIC_API_KEY"),
            },
        )

        fields: list[ConfigField] = [
            ConfigField(
                name="dev_mode",
                default_value=False,
                help_message="Adds to the python system path the current "
                "directory so addons can be developed.",
            ),
            ConfigField(
                name="show_horizontal_lines",
                default_value=True,
                help_message="True to print horizontal lines to segment the output. "
                "Makes it easier to read.",
            ),
            ConfigField(
                name="ai_custom",
                default_value=[],
                on_read=lambda cfg: config._load_custom_ai(cfg["ai_custom"]),
                error_message="Invalid custom AI specification",
            ),
            # This needs to be before "ai_model" - Loads the AI Models
            ConfigField(
                name="llm_requests.open_ai.model_refresh_seconds",
                # Default is to refresh once a day
                default_value=config._init_ai_models(86400),
                validate=lambda v: isinstance(v, int),
                on_load=config._init_ai_models,
                help_message="How often to refresh the models list provided by OpenAI. "
                "Make sure not to spam them as they can IP block. Default is once a day.",
                error_message="Invalid value, needs to be an int in seconds",
            ),
            # This needs to be processed after ai_custom
            ConfigField(
                name="ai_model",
                default_value=None,
                # Api keys are loaded from system env so they are already
                # available
                validate=lambda v: isinstance(v, str)
                and AIModels().is_valid_ai_model(v),
                on_load=AIModels().get_ai_model,
                help_message="Which AI model to use.",
            ),
            ConfigField(
                name="temp_auto_clean",
                default_value=True,
                validate=lambda v: isinstance(v, bool),
                help_message="Should the temporary files created be cleared automatically?",
            ),
            ConfigField(
                name="temp_file_dir",
                default_value=None,
                validate=lambda v: isinstance(v, str) and Path(v).is_file(),
                on_load=Path,
                default_value_none=True,
                help_message="Sets the directory to store temporary ESBMC-AI files. "
                "Don't supply a value to use the system default.",
            ),
            ConfigField(
                name="allow_successful",
                default_value=False,
                validate=lambda v: isinstance(v, bool),
                help_message="Run the ESBMC-AI command even if the verifier has not "
                "found any problems.",
            ),
            ConfigField(
                name="loading_hints",
                default_value=True,
                validate=lambda v: isinstance(v, bool),
                help_message="Show loading hints when running. Turn off if output "
                "is going to be logged to a file.",
            ),
            ConfigField(
                name="source_code_format",
                default_value="full",
                validate=lambda v: isinstance(v, str) and v in ["full", "single"],
                error_message="source_code_format can only be 'full' or 'single'",
                help_message="The source code format in the fix code prompt.",
            ),
            # This is the parameters that the user passes as args which are the
            # file names of the source code to target. It can also be a directory.
            ConfigField(
                name="solution.filenames",
                default_value=[],
                validate=lambda v: isinstance(v, list)
                # Validate config values are strings and also the paths exist
                and (
                    len(v) == 0
                    or all(isinstance(f, str) and Path(f).exists() for f in v)
                )
                # Validate arg values
                and (
                    len(config._args.filenames) == 0
                    or all(Path(f).exists() for f in config._args.filenames)
                ),
                on_load=config._filenames_load,
                get_error_message=config._filenames_error_msg,
            ),
            ConfigField(
                name="solution.include_dirs",
                default_value=[],
                validate=lambda v: isinstance(v, list)
                and all(
                    isinstance(f, str) and Path(f).exists() and Path(f).is_dir()
                    for f in v
                ),
                help_message="Include directories for C files.",
                on_load=lambda v: [Path(path) for path in v],
            ),
            # If argument is passed, then the config value is ignored.
            ConfigField(
                name="solution.entry_function",
                default_value=None,
                validate=lambda v: isinstance(v, str)
                and (
                    # This impliments logical implication A => B
                    # So if entry_function arg is set then it must be a string
                    not config._args.entry_function
                    or isinstance(config._args.entry_function, str)
                ),
                on_load=lambda v: (
                    config._args.entry_function
                    if config._args.entry_function != "main" or not v
                    else v
                ),
                error_message="The entry function name needs to be a string",
            ),
            ConfigField(
                name="verifier.enable_cache",
                default_value=True,
                help_message="Cache the results of verification in order to save time. "
                "This is not supported by all verifiers.",
            ),
            ConfigField(
                name="verifier.esbmc.path",
                default_value=None,
                validate=lambda v: isinstance(v, str)
                and Path(v).expanduser().is_file(),
                on_load=lambda v: Path(v).expanduser(),
                help_message="Path to the ESBMC binary.",
            ),
            ConfigField(
                name="verifier.esbmc.params",
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
                help_message="Parameters for ESBMC.",
            ),
            ConfigField(
                name="verifier.esbmc.output_type",
                default_value="full",
                validate=lambda v: v in ["full", "vp", "ce"],
                help_message="The type of output from ESBMC in the fix code command.",
            ),
            ConfigField(
                name="verifier.esbmc.timeout",
                default_value=None,
                default_value_none=True,
                validate=lambda v: v is None or isinstance(v, int),
                help_message="The timeout set for ESBMC.",
            ),
            ConfigField(
                name="llm_requests.max_tries",
                default_value=5,
                validate=lambda v: isinstance(v, int),
                help_message="How many times to query the AI service before giving up.",
            ),
            ConfigField(
                name="llm_requests.timeout",
                default_value=60,
                validate=lambda v: isinstance(v, int),
                help_message="The timeout for querying the AI service.",
            ),
            ConfigField(
                name="user_chat.temperature",
                default_value=1.0,
                validate=lambda v: isinstance(v, float) and 0 <= v <= 2.0,
                error_message="Temperature needs to be a value between 0 and 2.0",
                help_message="The temperature of the LLM for the user chat command.",
            ),
            ConfigField(
                name="fix_code.temperature",
                default_value=1.0,
                validate=lambda v: isinstance(v, float) and 0 <= v <= 2,
                error_message="Temperature needs to be a value between 0 and 2.0",
                help_message="The temperature of the LLM for the fix code command.",
            ),
            ConfigField(
                name="fix_code.max_attempts",
                default_value=5,
                validate=lambda v: isinstance(v, int),
                help_message="Fix code command max attempts.",
            ),
            ConfigField(
                name="fix_code.message_history",
                default_value="normal",
                validate=lambda v: v in ["normal", "latest_only", "reverse"],
                error_message='fix_code.message_history can only be "normal", '
                + '"latest_only", "reverse"',
                help_message="The type of history to be shown in the fix code command.",
            ),
            ConfigField(
                name="prompt_templates.user_chat.initial",
                default_value=None,
                validate=lambda v: isinstance(v, str),
                on_load=lambda v: HumanMessage(content=v),
                help_message="The initial prompt for the user chat command.",
            ),
            ConfigField(
                name="prompt_templates.user_chat.system",
                default_value=None,
                validate=_validate_prompt_template_conversation,
                on_load=list_to_base_messages,
                help_message="The system prompt for the user chat command.",
            ),
            ConfigField(
                name="prompt_templates.user_chat.set_solution",
                default_value=None,
                validate=_validate_prompt_template_conversation,
                on_load=list_to_base_messages,
                help_message="The prompt for the user chat command when a solution "
                "is found by the fix code command.",
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
                    scenario: FixCodeScenario(
                        initial=HumanMessage(content=conv["initial"]),
                        system=list_to_base_messages(conv["system"]),
                    )
                    for scenario, conv in config_file["prompt_templates"][
                        "fix_code"
                    ].items()
                },
                help_message="Scenario prompt templates for differnet types of bugs "
                "for the fix code command.",
            ),
        ]

        # Base init needs to be called last (only before load args)
        config.load_config_fields(config.get_value("ESBMCAI_CONFIG_FILE"), fields)
        config._load_args()

        # Config Pseudo-Entries - In the future have different type of config field
        # that won't be read from the config file.
        config.add_config_field(
            ConfigField(
                name="generate_patches",
                default_value=config.generate_patches,
                default_value_none=True,
                help_message="Should the repaired result be returned as a patch "
                "instead of a new file.",
            )
        )
        config.add_config_field(
            ConfigField(
                name="fix_code.raw_conversation",
                default_value=config.raw_conversation,
                default_value_none=True,
                help_message="Print the raw conversation at different parts of execution.",
            )
        )
        config.add_config_field(
            ConfigField(
                name="solution.output_dir",
                default_value=config.output_dir,
                default_value_none=True,
                help_message="Set the output directory to save successfully repaired "
                "files in. Leave empty to not use.",
            )
        )

    def _load_envs(self, *fields: ConfigField) -> None:
        """Loads the environment variables.
        Environment variables are loaded in the following order:

        1. Environment variables already loaded. Any variable not present will be looked for in
        .env files in the following locations.
        2. .env file in the current directory, moving upwards in the directory tree.
        3. esbmc-ai.env file in the current directory, moving upwards in the directory tree.
        4. esbmc-ai.env file in $HOME/.config/ for Linux/macOS and %userprofile% for Windows.

        Note: ESBMCAI_CONFIG_FILE undergoes tilde user expansion and also environment
        variable expansion.
        """

        for field in fields:
            assert (
                field.on_read is None
            ), f"ConfigField on_read for envs is not supported: {field.name}"

        keys: dict[str, ConfigField] = {field.name: field for field in fields}

        def get_env_vars() -> None:
            """Gets all the system environment variables that are currently in the env
            and loads them. Will only load keys that have not already been loaded."""
            for field_name, field in keys.items():
                value: str | None = os.getenv(field_name)

                # Assign field from config file
                self._values[field_name] = field.on_load(value)

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

        # Check all field values are set, if they aren't then error.
        for field_name, field in keys.items():
            # If field name is not loaded in the end...
            if field_name not in self._values:
                if field.default_value is None and not field.default_value_none:
                    print(f"Error: No ${field_name} in environment.")
                    sys.exit(1)
                self._values[field_name] = field.default_value

            # Validate field
            value: Any = self._values[field_name]
            if not field.validate(value):
                msg = f"Field: {field.name} is invalid: {value}"
                if field.get_error_message is not None:
                    msg += ": " + field.get_error_message(value)
                elif field.error_message:
                    msg += ": " + field.error_message
                raise ValueError(f"Env loading error: {msg}")

        self._fields.extend(fields)

    def _load_args(self) -> None:
        args: argparse.Namespace = self._args

        set_verbose(args.verbose)

        # AI Model -m
        if args.ai_model != "":
            if AIModels().is_valid_ai_model(args.ai_model):
                ai_model = AIModels().get_ai_model(args.ai_model)
                self.set_value("ai_model", ai_model)
            else:
                print(f"Error: invalid --ai-model parameter {args.ai_model}")
                sys.exit(4)

        self.raw_conversation = args.raw_conversation
        self.generate_patches = args.generate_patches

        if args.output_dir:
            path: Path = Path(args.output_dir).expanduser()
            if path.is_dir():
                self.output_dir = path
            else:
                print(
                    "Error while parsing arguments: output_dir: dir does not exist:",
                    self.output_dir,
                )
                sys.exit(1)

    def _validate_custom_ai(self, ai_config_list: dict) -> bool:
        for name, ai_config in ai_config_list.items():
            # Max tokens
            if "max_tokens" not in ai_config:
                raise KeyError(
                    f'max_tokens field not found in "ai_custom" entry "{name}".'
                )
            elif not isinstance(ai_config["max_tokens"], int):
                raise TypeError(
                    f'custom_ai_max_tokens in ai_custom entry "{name}" needs to '
                    "be an int and greater than 0."
                )
            elif ai_config["max_tokens"] <= 0:
                raise ValueError(
                    f'custom_ai_max_tokens in ai_custom entry "{name}" needs to '
                    "be an int and greater than 0."
                )

            # URL
            if "url" not in ai_config:
                raise KeyError(f'url field not found in "ai_custom" entry "{name}".')

            # Server type
            if "server_type" not in ai_config:
                raise KeyError(
                    f"server_type for custom AI '{name}' is invalid, it needs to be a valid string"
                )

        return True

    def _load_custom_ai(self, ai_config_list: dict) -> list[AIModel]:
        """Loads custom AI defined in the config and ascociates it with the AIModels
        module."""

        self._validate_custom_ai(ai_config_list)

        custom_ai: list[AIModel] = []
        for name, ai_config in ai_config_list.items():
            # Load the max tokens
            max_tokens: int = ai_config["max_tokens"]

            # Load the URL
            url: str = ai_config["url"]

            # Get provider type
            server_type = ai_config["server_type"]

            # Create correct type of LLM
            llm: AIModel
            match server_type:
                case "ollama":
                    llm = OllamaAIModel(
                        name=name,
                        tokens=max_tokens,
                        url=url,
                    )
                case _:
                    raise NotImplementedError(
                        f"The custom AI server type is not implemented: {server_type}"
                    )

            # Add the custom AI.
            custom_ai.append(llm)
            AIModels().add_ai_model(llm)

        return custom_ai

    def _filenames_load(self, file_names: list[str]) -> list[Path]:
        """Loads the filenames from the command line first then from the config."""

        results: list[Path] = []

        if len(self._args.filenames):
            results.extend(Path(f).absolute() for f in self._args.filenames)

        for file in file_names:
            results.append(Path(file).absolute())
        return results

    @staticmethod
    def _filenames_error_msg(file_names: list) -> str:
        """Gets the error message for an invalid list of file_names specified in
        the config."""

        wrong: list[str] = []
        for file_name in file_names:
            if not isinstance(file_name, str) or not (
                Path(file_name).is_file() or Path(file_name).is_dir()
            ):
                wrong.append(file_name)

        # Don't return the error because if there's too many files, the message
        # get's truncated.
        print("The following files or directories cannot be found:")
        for f in wrong:
            print("\t*", f)

        return "Error while loading files..."

    def _init_ai_models(self, refresh_duration: int) -> int:
        AIModels().load_models(self.get_value("api_keys"), refresh_duration)
        return refresh_duration
