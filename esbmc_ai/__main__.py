#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import logging
import sys

import argparse

from pydantic_core import ErrorDetails
from pydantic_settings import CliApp, CliSettingsSource
from pydantic_core._pydantic_core import ValidationError
from structlog import get_logger
from structlog.stdlib import BoundLogger

from esbmc_ai import Config, ChatCommand, __author__, __version__
from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.command_result import CommandResult
from esbmc_ai.log_utils import LogCategories, get_log_level, init_logging
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.esbmc import ESBMC
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
        "--verbose",
        action="count",
        default=0,
        help=(
            "Show up to 3 levels of verbose output. Level 1: extra information."
            " Level 2: show failed generations, show ESBMC output. Level 3: "
            "print hidden pushes to the message stack."
        ),
    )


def _load_config(
    parser: argparse.ArgumentParser,
) -> Config:
    # Check if help is requested - if so, skip verbose level extraction
    # and let CliApp.run handle the full help display with all Pydantic fields
    help_requested = "--help" in sys.argv or "-h" in sys.argv

    if not help_requested:
        # Parse args to get verbose level before Pydantic CLI parsing
        args, _ = parser.parse_known_args()
        verbose_level: int = min(args.verbose, 3) if hasattr(args, "verbose") else 0
    else:
        # No need to parse verbosity.
        verbose_level: int = 0

    # Create custom CLI settings source using our argparse parser
    # This allows us to use custom arguments like -v/--verbose with action='count'
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

    # Set argparse config values - These fields have exclude=True
    config.verbose_level = verbose_level

    return config


def _init_builtin_components() -> None:
    """Initializes the builtin verifiers and commands."""
    component_manager = ComponentManager()

    # Built-in verifiers
    esbmc = ESBMC.create()
    assert isinstance(esbmc, BaseSourceVerifier)
    component_manager.add_verifier(esbmc)
    # Load component-specific configuration
    component_manager.load_component_config(esbmc, builtin=True)

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
  * CLI args > Environment variables > .env file > TOML config > Defaults
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

    # Run the command
    command_name = config.command_name
    command_names: list[str] = cm.command_names
    if command_name in command_names:
        logger.info(f"Running Command: {command_name}\n")
        command: ChatCommand = cm.commands[command_name]
        result: CommandResult | None = command.execute()
        if result:
            if config.use_json:
                print(vars(result))
            else:
                print(result)

        sys.exit(0)
    else:
        logger.error(
            f"Error: Unknown command: {command_name}. Choose from: "
            + ", ".join(command_names)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
