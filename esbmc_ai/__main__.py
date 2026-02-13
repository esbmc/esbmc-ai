#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import json
import logging
import sys
from time import perf_counter

import argparse

from pydantic_core import ErrorDetails
from pydantic_settings import CliApp, CliSettingsSource
from pydantic_core._pydantic_core import ValidationError
from structlog import get_logger
from structlog.stdlib import BoundLogger

from esbmc_ai import Config, ChatCommand, __author__, __version__
from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.base_component import BaseComponent
from esbmc_ai.command_result import CommandResult
from esbmc_ai.log_utils import LogCategories, get_log_level, init_logging
from esbmc_ai.verifiers import BaseSourceVerifier, ESBMC, CommandOracle
from esbmc_ai.component_manager import ComponentManager
import esbmc_ai.commands


def _init_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help message and exit.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=__version__),
        help="Show version information.",
    )

    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help=argparse.SUPPRESS,  # Hidden from help, documented in --verbose
    )


def _load_config(
    parser: argparse.ArgumentParser,
) -> Config:
    # Check if help is requested - if so, skip verbose level extraction
    # and let CliApp.run handle the full help display with all Pydantic fields
    help_requested = "--help" in sys.argv or "-h" in sys.argv

    # Parse -v flag before pydantic to get the count
    args, _ = parser.parse_known_args()
    v_count: int | None = min(args.v, 3) if hasattr(args, "v") else None

    # Load the config

    # Create custom CLI settings source using our argparse parser
    # This allows us to use different arguments for argparse
    cli_settings: CliSettingsSource = CliSettingsSource(
        Config, cli_parse_args=True, root_parser=parser, cli_implicit_flags=True
    )

    # If help is requested and validation fails, catch error and show help anyway
    try:
        # Use CliApp.run with custom CLI settings source
        # settings_customise_sources will handle TOML/env/dotenv loading process
        config: Config = CliApp.run(Config, cli_settings_source=cli_settings)
    except ValidationError as e:
        if help_requested:
            # When help is requested, show help even if config validation fails
            # CliSettingsSource has already added all Pydantic fields to the parser
            parser.print_help()
            sys.exit(0)
        else:
            # Re-raise the exception if help was not requested
            print(f"ESBMC-AI: validation error while loading {e.title}\n")
            errs: list[ErrorDetails] = e.errors(
                include_context=True,
                include_input=True,
            )
            for idx, err in enumerate(errs):
                print(
                    f"* Error {idx}: "
                    f'{err["type"]}: {err["loc"]} cannot accept '
                    f'"{err["input"]}" (type {type(err["input"]).__name__}) '
                    f'because: {err["msg"]}'
                )
            print("\nShowing traceback...")
            print("=" * 80)
            raise

    # If help was requested and config loaded successfully, show help and exit
    # This handles the case where --help is passed but config validation succeeds
    if help_requested:
        parser.print_help()
        sys.exit(0)

    # Override verbose_level if -v flag was used
    if v_count:
        config.verbose_level = v_count

    return config


def _init_builtin_components() -> None:
    """Initializes the builtin verifiers and commands."""
    component_manager: ComponentManager = ComponentManager()

    # Built-in verifiers
    esbmc: BaseComponent = ESBMC.create()
    assert isinstance(esbmc, BaseSourceVerifier)
    component_manager.add_verifier(esbmc)
    component_manager.load_component_config(esbmc, builtin=True)

    generic_cmd: BaseComponent = CommandOracle.create()
    assert isinstance(generic_cmd, BaseSourceVerifier)
    component_manager.add_verifier(generic_cmd)
    component_manager.load_component_config(generic_cmd, builtin=True)

    # Init built-in commands - Loads everything in the esbmc_ai.commands module.
    commands: list[ChatCommand] = []
    for cmd_classname in getattr(esbmc_ai.commands, "__all__"):
        cmd_type: type = getattr(esbmc_ai.commands, cmd_classname)
        assert issubclass(cmd_type, ChatCommand), f"{cmd_type} is not a ChatCommand"
        cmd: object = cmd_type.create()
        assert isinstance(cmd, ChatCommand)
        cmd.global_config = Config()
        # Load component-specific configuration
        component_manager.load_component_config(cmd, builtin=True)
        commands.append(cmd)

    component_manager.set_builtin_commands(commands)


def _init_logging() -> None:
    # Add logging handlers with config options
    config = Config()
    logging_handlers: list[logging.Handler] = config.log.logging_handlers

    # Reinit logging
    init_logging(
        level=get_log_level(config.verbose_level),
        file_handlers=logging_handlers,
        init_basic=config.log.basic,
    )


def main() -> None:
    """Entry point function"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="ESBMC-AI",
        description="""Automated Program Repair platform. To view help on subcommands, run with the subcommand "help".

Configuration Precedence (highest to lowest):
  * CLI args > TOML config > Environment variables > .env file > Defaults
  * NOTE: Nested config values can be set via environment variables using double underscores
    (e.g., ESBMCAI_VERIFIER__ESBMC__PATH for verifier.esbmc.path)""",
        epilog=f"Made by {__author__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # Disable argparse help to let Pydantic handle full help display
        add_help=False,
    )

    _init_args(parser=parser)

    config: Config
    config = _load_config(parser=parser)
    # Set the config singleton
    Config.set_singleton(config)
    config: Config = Config()

    print(f"ESBMC-AI v{__version__}")
    print(f"Made by {__author__}")
    print()

    _init_logging()

    logger: BoundLogger = get_logger().bind(category=LogCategories.SYSTEM)
    logger.debug("Global config loaded successfully")
    logger.debug("Initialized logging")

    _init_builtin_components()
    logger.debug("Builtin components loaded successfully")

    if config.dev_mode:
        logger.warn("Development Mode Activated")

    # Load addons
    addon_loader: AddonLoader = AddonLoader(config)
    logger.debug("Addon components loaded successfully")
    logger.info("Configuration loaded successfully")

    # Bind addons to component loader.
    cm = ComponentManager()
    for command in addon_loader.chat_command_addons.values():
        cm.add_command(command, builtin=False)

    for verifier in addon_loader.verifier_addons.values():
        cm.add_verifier(verifier, builtin=False)

    cm.set_verifier_by_name(config.verifier.name)

    # Show full config at highest verbosity level (-vvv)
    if config.verbose_level >= 3:
        logger.debug("Global configuration:")
        print(json.dumps(config.model_dump(), indent=2, default=str))
        print()

    # Run the command
    command_name = config.command_name
    command_names: list[str] = cm.command_names
    if command_name in command_names:
        logger.info(f"Running Command: {command_name}\n")
        command: ChatCommand = cm.commands[command_name]

        # Show command config at highest verbosity level (-vvv)
        if config.verbose_level >= 3:
            try:
                cmd_config = command.config
                logger.debug(f"Command '{command_name}' configuration:")
                print(json.dumps(cmd_config.model_dump(), indent=2, default=str))
                print()
            except NotImplementedError:
                pass

        start_time: float = perf_counter()
        result: CommandResult | None = command.execute()
        time_taken: float = perf_counter() - start_time
        logger.info(f"Time taken: {time_taken}")

        if result:
            print(result)
            if config.use_json:
                json_result_str: str = result.to_json()
                json_result: dict = json.loads(json_result_str)
                json_result["time_taken_seconds"] = time_taken
                json_result_str = json.dumps(json_result)
                print(json_result_str)
                if config.json_path:
                    with open(config.json_path, "w", encoding="utf-8") as f:
                        f.write(json_result_str)

        sys.exit(0)
    else:
        logger.error(
            f"Error: Unknown command: {command_name}. Choose from: "
            + ", ".join(command_names)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
