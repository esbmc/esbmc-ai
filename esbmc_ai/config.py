# Author: Yiannis Charalambous 2023


from dataclasses import dataclass
import os
import sys
from platform import system as system_name
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from dotenv import load_dotenv, find_dotenv
from langchain.schema import HumanMessage

from esbmc_ai.config_field import ConfigField
from esbmc_ai.base_config import BaseConfig, default_scenario
from esbmc_ai.chat_response import list_to_base_messages
from esbmc_ai.logging import set_verbose
from .ai_models import (
    BaseMessage,
    is_valid_ai_model,
    get_ai_model_by_name,
    add_custom_ai_model,
    AIModel,
    OllamaAIModel,
)
from .api_key_collection import APIKeyCollection


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

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(Config, cls).__new__(cls)
        return cls.instance

    # Define some shortcuts for the values here (instead of having to use get_value)

    def get_ai_model(self) -> AIModel:
        """Value of field: ai_model"""
        return self.get_value("ai_model")

    def get_llm_requests_max_tries(self) -> int:
        """Value of field: llm_requests.max_tries"""
        return self.get_value("llm_requests.max_tries")

    def get_llm_requests_timeout(self) -> float:
        """"""
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

    def init(self, args: Any) -> None:
        """Will load the config from the args, the env file and then from config file.
        Call once to initialize."""

        fields: list[ConfigField] = [
            ConfigField(
                name="ai_custom",
                default_value=[],
                on_read=lambda cfg: self._load_custom_ai(cfg["ai_custom"]),
                error_message="Invalid custom AI specification",
            ),
            # This needs to be processed after ai_custom
            ConfigField(
                name="ai_model",
                default_value=None,
                # Api keys are loaded from system env so they are already
                # available
                validate=lambda v: isinstance(v, str)
                and is_valid_ai_model(v, self.api_keys),
                on_load=lambda v: get_ai_model_by_name(v, self.api_keys),
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
            ConfigField(
                name="verifier.esbmc.path",
                default_value=None,
                validate=lambda v: isinstance(v, str)
                and Path(v).expanduser().is_file(),
                on_load=lambda v: Path(v).expanduser(),
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
            ),
            ConfigField(
                name="verifier.esbmc.output_type",
                default_value="full",
                validate=lambda v: v in ["full", "vp", "ce"],
            ),
            ConfigField(
                name="verifier.esbmc.timeout",
                default_value=60,
                validate=lambda v: isinstance(v, int),
            ),
            ConfigField(
                name="tester",
                default_value="simple",
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
                    scenario: FixCodeScenario(
                        initial=HumanMessage(content=conv["initial"]),
                        system=list_to_base_messages(conv["system"]),
                    )
                    for scenario, conv in config_file["prompt_templates"][
                        "fix_code"
                    ].items()
                },
            ),
        ]

        self.api_keys: APIKeyCollection
        self.raw_conversation: bool = False
        self.generate_patches: bool
        self.output_dir: Optional[Path] = None

        self._load_envs()

        # Base init needs to be called last (only before load args)
        super().base_init(self.cfg_path, fields)
        self._load_args(args)

    def _load_envs(self) -> None:
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

        self.api_keys = APIKeyCollection(
            openai=str(os.getenv("OPENAI_API_KEY")),
        )

        self.cfg_path: Path = Path(
            os.path.expanduser(
                os.path.expandvars(str(os.getenv("ESBMCAI_CONFIG_PATH")))
            )
        )

    def _load_args(self, args) -> None:
        set_verbose(args.verbose)

        # AI Model -m
        if args.ai_model != "":
            if is_valid_ai_model(args.ai_model, self.api_keys):
                ai_model = get_ai_model_by_name(args.ai_model, self.api_keys)
                self.set_value("ai_model", ai_model)
            else:
                print(f"Error: invalid --ai-model parameter {args.ai_model}")
                sys.exit(4)

        # If append flag is set, then append.
        # FIXME Currently this will only work with esbmc not other verifiers
        if args.append:
            esbmc_params: List[str] = self.get_value("verifier.esbmc")
            esbmc_params.extend(args.remaining)
            self.set_value("verifier.esbmc", esbmc_params)
        elif len(args.remaining) != 0:
            self.set_value("verifier.esbmc", args.remaining)

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
            add_custom_ai_model(llm)

        return custom_ai
