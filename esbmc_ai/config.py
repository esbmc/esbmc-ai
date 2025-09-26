# Author: Yiannis Charalambous 2023


from importlib.machinery import ModuleSpec
from importlib.util import find_spec
import logging
import os
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from pydantic import (
    AliasChoices,
    BaseModel,
    DirectoryPath,
    Field,
    FilePath,
    field_validator,
)

from esbmc_ai.singleton import SingletonMeta, makecls
from esbmc_ai.log_handlers import (
    CategoryFileHandler,
    NameFileHandler,
)


class AICustomModelConfig(BaseModel):
    server_type: str
    url: str
    max_tokens: int


class LogConfig(BaseModel):
    output: FilePath | None = Field(
        default=None,
        description="Save the output logs to a location. Do not add "
        ".log suffix, it will be added automatically.",
    )

    append: bool = Field(
        default=False,
        description="Will append to the logs rather than replace them.",
    )

    by_cat: bool = Field(
        default=False,
        description="Will split the logs by category and write them to"
        " different files. They will have the same base log.output path"
        " but will have an extension to differentiate them.",
    )

    by_name: bool = Field(
        default=False,
        description="Will split the logs by name and write them to"
        " different files. They will have the same base log.output path"
        " but will have an extension to differentiate them.",
    )

    basic: bool = Field(
        default=False,
        description="Enable basic logging mode, will contain no "
        "formatting and also will render --log-by-name (log.by_name) "
        "and --log-by-cat (log.by_cat) useless. Used for debugging "
        "noisy libs.",
    )

    @property
    def logging_handlers(self) -> list[logging.Handler]:
        logging_handlers: list[logging.Handler] = []
        if self.output:
            # Log categories
            if self.by_cat:
                logging_handlers.append(
                    CategoryFileHandler(
                        self.output,
                        append=self.append,
                        skip_uncategorized=True,
                    )
                )
            # Log by name
            if self.by_name:
                logging_handlers.append(
                    NameFileHandler(
                        self.output,
                        append=self.append,
                    )
                )

            # Normal logging
            file_log_handler: logging.Handler = logging.FileHandler(
                str(self.output) + ".log",
                mode="a" if self.append else "w",
            )
            logging_handlers.append(file_log_handler)
        return logging_handlers


class SolutionConfig(BaseModel):
    filenames: list[FilePath | DirectoryPath] = Field(
        default_factory=list,
        alias="filenames",
    )

    @field_validator("filenames", mode="after")
    @classmethod
    def on_set_filenames(cls, value: list[FilePath]) -> list[FilePath]:
        """Validates that all the filenames are file paths or is one directory
        path."""
        file_count: int = 0
        for v in value:
            if isinstance(v, Path) and v.exists():
                if v.is_file():
                    file_count += 1
                elif v.is_dir() and file_count != 0:
                    raise ValueError(
                        "filenames needs to be all file paths or " "one directory path"
                    )

        return value

    include_dirs: list[DirectoryPath] = Field(
        default_factory=list,
        description="Include directories for C files.",
    )

    entry_function: str = Field(
        default="main",
        description="The name of the entry function to repair, defaults to main.",
    )

    output_dir: DirectoryPath | None = Field(
        default=None,
        description="Set the output directory to save successfully repaired "
        "files in. Leave empty to not use. Specifying the same directory will "
        "overwrite the original file.",
    )

    @field_validator("output_dir", mode="before")
    @classmethod
    def on_set_output_dir(cls, value: DirectoryPath | None) -> DirectoryPath | None:
        if value is None:
            return None
        return Path(value).expanduser()


class VerifierConfig(BaseModel):

    # The value is checked in AddonLoader.
    name: str = Field(
        default="esbmc",
        description="The verifier to use. Default is ESBMC.",
    )

    enable_cache: bool = Field(
        default=True,
        description="Cache the results of verification in order to save time. "
        "This is not supported by all verifiers.",
    )

    esbmc_path: FilePath | None = Field(
        default=None,
        validation_alias="esbmc.path",
        description="Path to the ESBMC binary.",
    )

    esbmc_params: list[str] = Field(
        validation_alias="esbmc.params",
        default=[
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
        description="Parameters for ESBMC. Can accept as a list or a string.",
    )

    esbmc_timeout: int | None = Field(
        default=None,
        validation_alias="esbmc.timeout",
        description="The timeout set for ESBMC.",
    )


class Config(BaseSettings, metaclass=makecls(SingletonMeta)):
    """Config loader for ESBMC-AI"""

    config_file: FilePath | None = Field(
        default=None,
        exclude=True,
        description="Path to configuration file (TOML format). Can be set via ESBMCAI_CONFIG_FILE environment variable.",
    )

    command_name: str = Field(
        default="help",
        alias="command",
        exclude=True,
        description="The (sub-)command to run.",
    )

    addon_modules: list[str] = Field(
        default_factory=list,
        description="The addon modules to load during startup. Additional "
        "modules may be loaded by the specified modules as dependencies.",
    )

    @field_validator("addon_modules", mode="after")
    @classmethod
    def on_set_addon_modules(cls, mods: list[str]) -> list[str]:
        """Validates that a module exists."""
        for m in mods:
            if not isinstance(m, str):
                raise ValueError("Needs to be a string")
            spec: ModuleSpec | None = find_spec(m)
            if spec is None:
                raise ValueError("Could not find specification for module")
        return mods

    verbose_level: int = Field(
        default=0,
        ge=0,
        le=3,
        validation_alias="verbose",
        description="Show up to 3 levels of verbose output. Level 1: extra information."
        " Level 2: show failed generations, show ESBMC output. Level 3: "
        "print hidden pushes to the message stack.",
    )

    dev_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("dev_mode", "dev-mode"),
        description="Adds to the python system path the current "
        "directory so addons can be developed.",
    )

    use_json: bool = Field(
        default=False,
        alias="json",
        description="Print the result of the chat command as a JSON output",
    )

    show_horizontal_lines: bool = Field(
        default=True,
        validation_alias=AliasChoices("show_horizontal_lines", "show-horizontal-lines"),
        description="True to print horizontal lines to segment the output. "
        "Makes it easier to read.",
    )

    horizontal_line_width: int | None = Field(
        default=None,
        validation_alias="horizontal_line_width",
        description="Sets the width of the horizontal lines to draw. "
        "Don't set a value to use the terminal width. Needs to have "
        "show_horizontal_lines set to true.",
    )

    ai_custom: dict[str, AICustomModelConfig] = Field(
        default_factory=dict,
        description=(
            "Dictionary of Ollama AI models configurations. "
            "Each key is a model name (arbitrary string), and each value is a "
            "structure defining the model with the following fields:\n"
            " - server_type: string, must be 'ollama'\n"
            " - url: string specifying the Ollama service URL\n"
            " - max_tokens: integer specifying the token limit"
        ),
    )

    @field_validator("ai_custom", mode="after")
    @classmethod
    def _validate_custom_ai(cls, ai_config_list: dict) -> bool:
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

    ai_model: str = Field(
        default="openai:gpt-4.5-nano",
        validation_alias=AliasChoices("ai_model", "ai-model"),
        description="Which AI model to use. Prefix with openai, anthropic, or "
        "ollama then separate with : and enter the model name to use.",
    )

    temp_auto_clean: bool = Field(
        default=True,
        validation_alias=AliasChoices("temp_auto_clean", "temp-auto-clean"),
        description="Should the temporary files created be cleared automatically?",
    )

    temp_file_dir: DirectoryPath = Field(
        default=Path("/tmp"),
        validation_alias=AliasChoices("temp_file_dir", "temp-file-dir"),
        description="Sets the directory to store temporary ESBMC-AI files. "
        "Don't supply a value to use the system default.",
    )

    loading_hints: bool = Field(
        default=False,
        validation_alias=AliasChoices("loading_hints", "loading-hints"),
        description="Show loading hints when running. Turn off if output "
        "is going to be logged to a file.",
    )

    generate_patches: bool = Field(
        default=False,
        validation_alias=AliasChoices("generate_patches", "generate-patches"),
        description="Should the repaired result be returned as a patch "
        "instead of a new file. Generate patch files and place them in "
        "the same folder as the source files.",
    )

    log: LogConfig = Field(
        default_factory=LogConfig,
        description="Logging configuration group.",
    )

    solution: SolutionConfig = Field(
        default_factory=SolutionConfig,
        description="Solution config group.",
    )

    verifier: VerifierConfig = Field(
        default_factory=VerifierConfig,
        description="Verifier config group.",
    )

    llm_requests_max_retries: int = Field(
        default=5,
        ge=1,
        validation_alias="llm_requests.max_retries",
        description="How many times to query the AI service before giving up.",
    )

    llm_requests_timeout: int = Field(
        default=60,
        ge=1,
        validation_alias="llm_requests.timeout",
        description="The timeout for querying the AI service.",
    )

    model_config = SettingsConfigDict(
        env_prefix="ESBMCAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        # Enables CLI parse support out-of-the-box for CliApp.run integration
        cli_parse_args=True,
        # Allow extra fields for compatibility with pydantic_settings, since .env contains fields for services like OpenAI and Anthropic that isn't mapped to the config directly
        extra="ignore",
    )

    def __init__(self, **kwargs) -> None:
        # Accept keyword arguments to support pydantic_settings CliApp.run()
        # which passes settings_sources and other configuration parameters.
        # The singleton metaclass intercepts the constructor call and needs
        # to pass these arguments through to BaseSettings.__init__().
        super().__init__(**kwargs)

        # Huggingface warning supress
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

    @classmethod
    def set_singleton(cls, config: "Config") -> None:
        """Sets the singleton."""
        print("DEBUG! Singleton set")
        getattr(cls, "_instances")[cls] = config
