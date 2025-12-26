# Author: Yiannis Charalambous 2023


from collections import defaultdict
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
import logging
import os
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    CliPositionalArg,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing import Annotated
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
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


def _alias_choice(value: str) -> AliasChoices:
    """Adds aliases to each option that requires a different alias that works
    with all the config setting sources we are using.

    For nested fields, the double underscore notation (e.g., ESBMCAI_VERIFIER__ESBMC__PATH)
    is handled automatically by pydantic_settings via env_nested_delimiter='__'.
    """
    return AliasChoices(
        value,  # exact field name for TOML and direct matching
        value.replace("_", "-"),  # dashed alias for CLI or other uses
        f"ESBMCAI_{value.replace('-', '_').upper()}",  # prefixed env var alias
    )


class AIModelConfig(BaseModel):
    id: str = Field(
        default="openai:gpt-5-nano",
        validation_alias=_alias_choice("ai_model"),
        description="Which AI model to use. Prefix with openai, anthropic, or "
        "ollama then separate with : and enter the model name to use.",
    )

    base_url: str | None = Field(
        default=None,
        exclude=True,
        description="Gets initialized by the config if this model is an Ollama model.",
    )

    @property
    def provider(self) -> str:
        """The provider part of a model string."""
        return self.id.split(":", maxsplit=1)[0]

    @property
    def name(self) -> str:
        """The name part of a model string."""
        return self.id.split(":", maxsplit=1)[1]


class AICustomModelConfig(BaseModel):
    server_type: str
    url: str
    max_tokens: int


class LogConfig(BaseModel):
    output: Path | None = Field(
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
    filenames: CliPositionalArg[list[Path]] = Field(
        default_factory=list,
        description="The filename(s) to pass to the verifier.",
    )

    @field_validator("filenames", mode="after")
    @classmethod
    def on_set_filenames(cls, value: list[str]) -> list[Path]:
        """Validates that filenames are either all file paths or a single directory path."""
        if not value:
            return []

        paths: list[Path] = []
        files: list[str] = []
        dirs: list[str] = []

        for filename in value:
            path = Path(filename).expanduser()

            # Check if path exists
            if not path.exists():
                raise ValueError(f"File or directory not found: '{filename}'")

            # Categorize as file or directory
            if path.is_file():
                files.append(filename)
                paths.append(path)
            elif path.is_dir():
                dirs.append(filename)
                paths.append(path)
            else:
                raise ValueError(
                    f"Path exists but is neither a file nor directory: '{filename}'"
                )

        # Validate: either all files OR single directory
        if dirs and files:
            raise ValueError(
                f"Cannot mix files and directories. Either provide file paths or a single directory.\n"
                f"  Files provided: {', '.join(files)}\n"
                f"  Directories provided: {', '.join(dirs)}"
            )

        if len(dirs) > 1:
            raise ValueError(
                f"Only one directory can be specified. Got {len(dirs)} directories: {', '.join(dirs)}"
            )

        return paths

    include_dirs: list[DirectoryPath] = Field(
        default_factory=list,
        description="Include directories for C files.",
    )

    entry_function: str = Field(
        default="main",
        description="The name of the entry function to repair, defaults to main.",
    )

    output_dir: Path | None = Field(
        default=None,
        description="Set the output directory to save successfully repaired "
        "files in. Leave empty to not use. Specifying the same directory will "
        "overwrite the original file.",
    )

    @field_validator("output_dir", mode="before")
    @classmethod
    def on_set_output_dir(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        return Path(value).expanduser()

    @field_validator("output_dir", mode="after")
    @classmethod
    def on_after_set_output_dir(cls, value: Path | None) -> Path | None:
        """Creates the directory if it is missing."""
        if value is None:
            return None

        value.mkdir(mode=0o750, parents=True, exist_ok=True)
        return value


class ESBMCConfig(BaseModel):
    """ESBMC-specific configuration.

    Environment variables use double underscore notation for nesting:
    - ESBMCAI_VERIFIER__ESBMC__PATH (handled automatically via env_nested_delimiter)
    """

    path: FilePath | None = Field(
        default=None,
        description="Path to the ESBMC binary.",
    )

    @field_validator("path", mode="before")
    @classmethod
    def on_set_path(cls, value: FilePath | None) -> Path | None:
        if value is None:
            return None
        return Path(value).expanduser()

    params: list[str] = Field(
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
            "--context-bound",
            "2",
        ],
        description="Parameters for ESBMC. Can accept as a list or a string.",
    )

    timeout: int | None = Field(
        default=20,
        description="The timeout set for ESBMC.",
    )


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

    esbmc: ESBMCConfig = Field(
        default_factory=ESBMCConfig,
        description="ESBMC-specific configuration.",
    )


def _parse_ai_model(value: str | dict | AIModelConfig) -> AIModelConfig:
    """Validator function to convert string/dict to AIModelConfig."""
    # If it's already an AIModelConfig, return as-is
    if isinstance(value, AIModelConfig):
        return value
    # If it's a string, create AIModelConfig with validation_alias key
    if isinstance(value, str):
        return AIModelConfig(**{"ai_model": value})
    # If it's a dict, create AIModelConfig from it
    return AIModelConfig(**value)


class Config(BaseSettings, metaclass=makecls(SingletonMeta)):
    """Config loader for ESBMC-AI"""

    config_file: FilePath | None = Field(
        default=None,
        exclude=True,
        description="Path to configuration file (TOML format). Can be set via "
        "ESBMCAI_CONFIG_FILE environment variable.",
    )

    command_name: CliPositionalArg[str] = Field(
        default="help",
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
        import sys

        # Temporarily add current directory to sys.path for dev mode addon
        # discovery. This mirrors what AddonLoader does, but we need it here for
        # validation. AddonLoader will add the cwd if needed.
        added_cwd = False
        if "" not in sys.path:
            sys.path.insert(0, "")
            added_cwd = True

        try:
            for m in mods:
                if not isinstance(m, str):
                    raise ValueError("Needs to be a string")
                spec: ModuleSpec | None = find_spec(m)
                if spec is None:
                    raise ValueError(
                        f"Could not find specification for module '{m}'. "
                        "Ensure the module is installed or available in the "
                        "current directory."
                    )
        finally:
            # Clean up: remove the path we added
            if added_cwd and "" in sys.path:
                sys.path.remove("")

        return mods

    verbose_level: int = Field(
        default=0,
        ge=0,
        le=3,
        exclude=True,  # Exclude from Pydantic CLI parsing
        description="Show up to 3 levels of verbose output. Level 1: extra information."
        " Level 2: show failed generations, show ESBMC output. Level 3: "
        "print hidden pushes to the message stack.",
    )

    dev_mode: bool = Field(
        default=False,
        validation_alias=_alias_choice("dev_mode"),
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
        validation_alias=_alias_choice("show_horizontal_lines"),
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
        default_factory=defaultdict,
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
    def _validate_custom_ai(
        cls, ai_config_list: dict[str, AICustomModelConfig]
    ) -> dict[str, AICustomModelConfig]:
        for name, ai_config in ai_config_list.items():
            # If already an AICustomModelConfig instance, validate its fields
            if isinstance(ai_config, AICustomModelConfig):
                if ai_config.max_tokens <= 0:
                    raise ValueError(
                        f'max_tokens in ai_custom entry "{name}" needs to be greater than 0.'
                    )
            else:
                # If it's a dict, validate the dict structure
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
                        f'max_tokens in ai_custom entry "{name}" needs to be an int and greater than 0.'
                    )
                elif ai_config["max_tokens"] <= 0:
                    raise ValueError(
                        f'max_tokens in ai_custom entry "{name}" needs to be greater than 0.'
                    )

                # URL
                if "url" not in ai_config:
                    raise KeyError(
                        f'url field not found in "ai_custom" entry "{name}".'
                    )

                # Server type
                if "server_type" not in ai_config:
                    raise KeyError(
                        f"server_type for custom AI '{name}' is invalid, it needs to be a valid string"
                    )

        return ai_config_list

    ai_model: Annotated[AIModelConfig, NoDecode, BeforeValidator(_parse_ai_model)] = (
        Field(
            default_factory=AIModelConfig,
            description="AI Model configuration group. Can be a string like 'openai:gpt-4' or a config object.",
        )
    )

    temp_auto_clean: bool = Field(
        default=True,
        validation_alias=_alias_choice("temp_auto_clean"),
        description="Should the temporary files created be cleared automatically?",
    )

    temp_file_dir: DirectoryPath = Field(
        default=Path("/tmp"),
        validation_alias=_alias_choice("temp_file_dir"),
        description="Sets the directory to store temporary ESBMC-AI files. "
        "Don't supply a value to use the system default.",
    )

    loading_hints: bool = Field(
        default=False,
        validation_alias=_alias_choice("loading_hints"),
        description="Show loading hints when running. Turn off if output "
        "is going to be logged to a file.",
    )

    generate_patches: bool = Field(
        default=False,
        validation_alias=_alias_choice("generate_patches"),
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
        # Use double underscores for nested config fields in env vars
        # e.g., ESBMCAI_VERIFIER__ESBMC__PATH
        env_nested_delimiter="__",
        # Enables CLI parse support out-of-the-box for CliApp.run integration
        cli_parse_args=True,
        # Allow extra fields for compatibility with pydantic_settings, since
        # .env contains fields for services like OpenAI and Anthropic that isn't
        # mapped to the config directly
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type["BaseSettings"],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Manually load .env file to get ESBMCAI_CONFIG_FILE before creating sources
        from dotenv import load_dotenv

        load_dotenv(".env", override=False)

        # Get config file path from environment variable
        config_file_path = os.getenv("ESBMCAI_CONFIG_FILE")

        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
        ]

        # Add TOML config source if config file is specified (high priority)
        if config_file_path:
            config_file = Path(config_file_path).expanduser()
            if config_file.exists():
                sources.append(TomlConfigSettingsSource(settings_cls, config_file))

        # Add environment-based sources
        sources.extend([
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ])

        # Priority order: init/CLI > TOML > env > dotenv > file_secret
        return tuple(sources)

    def __init__(self, **kwargs) -> None:
        # Accept keyword arguments to support pydantic_settings CliApp.run()
        # which passes settings_sources and other configuration parameters.
        # The singleton metaclass intercepts the constructor call and needs
        # to pass these arguments through to BaseSettings.__init__().
        super().__init__(**kwargs)

        # Populate ai_model.base_url from ai_custom if model exists there
        if self.ai_model.id in self.ai_custom:
            self.ai_model.base_url = self.ai_custom[self.ai_model.id].url

    @classmethod
    def set_singleton(cls, config: "Config") -> None:
        """Sets the singleton."""
        getattr(cls, "_instances")[cls] = config
