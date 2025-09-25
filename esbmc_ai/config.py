# Author: Yiannis Charalambous 2023


import argparse
import logging
import os
import sys
from platform import system as system_name
from pathlib import Path
from typing import (
    Any,
    override,
)
import argparse

from dotenv import load_dotenv, find_dotenv
import structlog

from esbmc_ai.chats.base_chat_interface import BaseChatInterface
from esbmc_ai.singleton import SingletonMeta, makecls
from esbmc_ai.config_field import ConfigField
from esbmc_ai.base_config import BaseConfig
from esbmc_ai.log_utils import (
    CategoryFileHandler,
    LogCategories,
    NameFileHandler,
    get_log_level,
    init_logging,
    set_horizontal_lines,
    set_horizontal_line_width,
)
from esbmc_ai.ai_models import (
    AIModel,
    AIModelAnthropic,
    AIModelOpenAI,
    AIModels,
    OllamaAIModel,
)


class Config(BaseConfig, metaclass=makecls(SingletonMeta)):
    """Config loader for ESBMC-AI"""

    def __init__(self) -> None:

        super().__init__()

        self._args: argparse.Namespace
        self._arg_mappings: dict[str, list[str]] = {}
        self._compound_load_args: list[str] = []
        self._logger: structlog.stdlib.BoundLogger

        # Huggingface warning supress
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        # Even though this gets initialized when we call self.load_config_fields
        # it should be fine because load_config_field wont double add.
        self._config_fields = [
            ConfigField(
                name="dev_mode",
                default_value=False,
                help_message="Adds to the python system path the current "
                "directory so addons can be developed.",
            ),
            ConfigField(
                name="json",
                default_value=False,
                help_message="Print the result of the chat command as a JSON output",
            ),
            ConfigField(
                name="show_horizontal_lines",
                default_value=True,
                on_load=set_horizontal_lines,
                help_message="True to print horizontal lines to segment the output. "
                "Makes it easier to read.",
            ),
            ConfigField(
                name="horizontal_line_width",
                default_value=None,
                default_value_none=True,
                on_load=set_horizontal_line_width,
                help_message="Sets the width of the horizontal lines to draw. "
                "Don't set a value to use the terminal width. Needs to have "
                "show_horizontal_lines set to true.",
            ),
            ConfigField(
                name="ai_custom",
                default_value=[],
                on_read=self.load_custom_ai,
                error_message="Invalid custom AI specification",
            ),
            ConfigField(
                name="llm_requests.model_refresh_seconds",
                # Default is to refresh once a day
                default_value=86400,
                validate=lambda v: isinstance(v, int),
                help_message="How often to refresh the models list provided by OpenAI. "
                "Make sure not to spam them as they can IP block. Default is once a day.",
                error_message="Invalid value, needs to be an int in seconds",
            ),
            ConfigField(
                name="llm_requests.cooldown_seconds",
                default_value=0.0,
                validate=lambda v: 0 <= v,
                help_message="Cooldown applied in seconds between LLM requests.",
            ),
            ConfigField(
                name="ai_model",
                default_value=None,
                validate=lambda v: isinstance(v, str),
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
                default_value=False,
                validate=lambda v: isinstance(v, bool),
                help_message="Show loading hints when running. Turn off if output "
                "is going to be logged to a file.",
            ),
            ConfigField(
                name="generate_patches",
                default_value=False,
                help_message="Should the repaired result be returned as a patch "
                "instead of a new file. Generate patch files and place them in "
                "the same folder as the source files.",
            ),
            ConfigField(
                name="log.output",
                default_value=None,
                default_value_none=True,
                validate=lambda v: Path(v).exists() or Path(v).parent.exists(),
                on_load=lambda v: Path(v),
                help_message="Save the output logs to a location. Do not add "
                ".log suffix, it will be added automatically.",
            ),
            ConfigField(
                name="log.append",
                default_value=False,
                help_message="Will append to the logs rather than replace them.",
            ),
            ConfigField(
                name="log.by_cat",
                default_value=False,
                help_message="Will split the logs by category and write them to"
                " different files. They will have the same base log.output path"
                " but will have an extension to differentiate them.",
            ),
            ConfigField(
                name="log.by_name",
                default_value=False,
                help_message="Will split the logs by name and write them to"
                " different files. They will have the same base log.output path"
                " but will have an extension to differentiate them.",
            ),
            ConfigField(
                name="log.basic",
                default_value=False,
                help_message="Enable basic logging mode, will contain no "
                "formatting and also will render --log-by-name (log.by_name) "
                "and --log-by-cat (log.by_cat) useless. Used for debugging "
                "noisy libs.",
            ),
            # This is the parameters that the user passes as args which are the
            # file names of the source code to target. It can also be a directory.
            ConfigField(
                name="solution.filenames",
                default_value=[],
                validate=lambda v: isinstance(v, list)
                and (
                    len(v) == 0
                    or all(isinstance(f, str) and Path(f).exists() for f in v)
                ),
                on_load=self._filenames_load,
                get_error_message=self._filenames_error_msg,
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
                default_value="main",
                error_message="The entry function name needs to be a string",
                help_message="The name of the entry function to repair, defaults to main.",
            ),
            ConfigField(
                name="solution.output_dir",
                default_value=None,
                default_value_none=True,
                validate=lambda v: Path(v).exists() and Path(v).is_dir(),
                on_load=lambda v: Path(v).expanduser(),
                error_message="Dir does not exist",
                help_message="Set the output directory to save successfully repaired "
                "files in. Leave empty to not use. Specifying the same directory will "
                "overwrite the original file.",
            ),
            # The value is checked in AddonLoader.
            ConfigField(
                name="verifier.name",
                default_value="esbmc",
                validate=lambda v: isinstance(v, str),
                error_message="Invalid verifier name specified.",
                help_message="The verifier to use. Default is ESBMC.",
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
                on_load=lambda v: Path(os.path.expanduser(os.path.expandvars(v))),
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
                validate=lambda v: isinstance(v, list | str),
                on_load=lambda v: [
                    str(arg) for arg in (v.split(" ") if isinstance(v, str) else v)
                ],
                help_message="Parameters for ESBMC. Can accept as a list or a string.",
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
        ]

    def load(
        self,
        args: Any,
        arg_mapping_overrides: dict[str, list[str]],
        compound_load_args: list[str],
    ) -> None:
        """Begins the loading procedure to load the configuration.

        1. Environment variables
        2. Arguments (the arguments are mapped 1:1 to the config file, if there
        is a difference in mapping it is specified in the arg_mapping_overrides).
        Some config fields should be loaded when the config file has been loaded
        too, so defer_loading_args should have a list of argument names to skip
        and defer the loading behaviour to the config file loading. This process
        is not automated, so the respective ConfigField should specify how to
        load from the args.

        Args:
            - args: The values from the argument parser. They will take precedence
                over the config file.
            - arg_mapping_overrides: A dictionary that maps configuration field
                IDs to custom argument names. Use this to override the default
                mapping, allowing arguments to have names different from their
                corresponding configuration fields.
            - compound_load_fields: A list of argument names that,
                when supplied, should be loaded from both command-line arguments
                and a config file.
        """

        self._args = args
        # Create an argument mapping of all the config files, the arg_mapping is
        # applied over that to translate the mappings from the arguments to the
        # mappings of the config fields.
        self._arg_mappings = {
            f.name: [f.name] for f in self.get_config_fields()
        } | arg_mapping_overrides
        self._compound_load_args = compound_load_args

        # Init logging
        init_logging(level=get_log_level(args.verbose))
        self._logger = structlog.get_logger().bind(category=LogCategories.CONFIG)

        # Load config fields from environment
        self._load_envs(
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

        fields: list[ConfigField] = self.get_config_fields()
        self._load_args(args, fields)
        # Base init needs to be called last
        self.load_config_fields(self.get_value("ESBMCAI_CONFIG_FILE"), fields)

        # =============== Post Init - Set to good values to fields ============
        # Add logging handlers with config options
        logging_handlers: list[logging.Handler] = []
        if self.get_value("log.output"):
            log_path: Path = self.get_value("log.output")
            # Log categories
            if self.get_value("log.by_cat"):
                logging_handlers.append(
                    CategoryFileHandler(
                        log_path,
                        append=self.get_value("log.append"),
                        skip_uncategorized=True,
                    )
                )
            # Log by name
            if self.get_value("log.by_name"):
                logging_handlers.append(
                    NameFileHandler(
                        log_path,
                        append=self.get_value("log.append"),
                    )
                )

            # Normal logging
            file_log_handler: logging.Handler = logging.FileHandler(
                str(log_path) + ".log",
                mode="a" if self.get_value("log.append") else "w",
            )
            logging_handlers.append(file_log_handler)

        # Reinit logging
        init_logging(
            level=get_log_level(args.verbose),
            file_handlers=logging_handlers,
            init_basic=self.get_value("log.basic"),
        )

        self.set_custom_field(
            ConfigField(
                name="api_keys",
                default_value={},
            ),
            value={
                AIModelOpenAI.get_canonical_name(): self.get_value("OPENAI_API_KEY"),
                AIModelAnthropic.get_canonical_name(): self.get_value(
                    "ANTHROPIC_API_KEY"
                ),
            },
        )
        # Load AI models and set ai_model
        AIModels().load_default_models(
            self.get_value("api_keys"),
            self.get_value("llm_requests.model_refresh_seconds"),
        )
        self.set_value("ai_model", AIModels().get_ai_model(self.get_value("ai_model")))
        # BaseChatInterface cooldown
        BaseChatInterface.cooldown_total = self.get_value(
            "llm_requests.cooldown_seconds"
        )
        self._logger.debug(f"LLM Cooldown Total: {BaseChatInterface.cooldown_total}")

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

    @property
    def _arg_reverse_mappings(self) -> dict[str, str]:
        """Returns the reverse mapping of arg mappings. args --> field

        This also replaces all the - with _ in the names since this is done by
        argparse, for example: --ai-model will be accessible through ai_model."""
        reverse_mappings: dict[str, str] = {}
        for field_name, mappings in self._arg_mappings.items():
            for mapping in mappings:
                reverse_mappings[mapping.replace("-", "_")] = field_name

        return reverse_mappings

    def _load_args(self, args: argparse.Namespace, fields: list[ConfigField]) -> None:
        """Will load the fields set in the program arguments."""

        # Track the names of the fields set, fields that are already set are
        # skipped: --ai-models and -m are treated as one this way.
        fields_set: set[str] = set()
        reverse_mappings: dict[str, str] = self._arg_reverse_mappings
        fields_mapped: dict[str, ConfigField] = {f.name: f for f in fields}
        for mapped_name, value in vars(args).items():
            # Check if a field is set in args
            if mapped_name in reverse_mappings:
                # Get the field name
                field_name: str = reverse_mappings[mapped_name]
                # Skip if added
                if field_name in fields_set:
                    continue

                self._logger.debug(f"Loading from arg: {field_name}")

                fields_set.add(field_name)
                # Load with value.
                self.set_custom_field(fields_mapped[field_name], value)

    @override
    def load_config_fields(self, cfg_path: Path, fields: list[ConfigField]) -> None:
        """Override to only load fields that have not been loaded by the args."""

        # Track the names of the fields set, fields that are already set are
        # skipped: --ai-models and -m are treated as one this way.
        fields_set: set[str] = set()
        reverse_mappings: dict[str, str] = self._arg_reverse_mappings

        for mapped_name in vars(self._args).keys():
            # Check if a field is set in args (exclude if in compound load list)
            if (
                mapped_name in reverse_mappings
                and mapped_name not in self._compound_load_args
            ):
                # Get the field name
                fields_set.add(reverse_mappings[mapped_name])

        load_fields: list[ConfigField] = [f for f in fields if f.name not in fields_set]
        return super().load_config_fields(cfg_path, load_fields)

    def _filenames_load(self, file_names: list[str]) -> list[Path]:
        """Loads the filenames from the command line first then from the config."""

        results: list[Path] = []

        if len(self._args.filenames):
            results.extend(Path(f) for f in self._args.filenames)

        for file in file_names:
            results.append(Path(file))

        return results

    def _validate_custom_ai(self, ai_config_list: dict) -> bool:
        for name, ai_config in ai_config_list.items():
            # Check the field is a dict not a list
            if not isinstance(ai_config, dict):
                raise ValueError(
                    f"The value of each entry in ai_custom needs to be a dict: {ai_config}"
                )

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

    def load_custom_ai(self, config_file: dict) -> list[AIModel]:
        """Loads custom AI defined in the config and ascociates it with the AIModels
        module."""

        if "ai_custom" not in config_file:
            return []

        ai_config_list: dict = config_file["ai_custom"]
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

    def get_config_fields(self) -> list[ConfigField]:
        """Returns the config fields. Excluding env fields."""
        return self._config_fields
