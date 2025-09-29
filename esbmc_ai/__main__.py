#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import logging
import os
import sys
from pathlib import Path

import readline
import argparse

from pydantic_settings import (
    CliApp,
    CliSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
    DotEnvSettingsSource,
)
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

# Enables arrow key functionality for input(). Do not remove import.
_ = readline

HELP_MESSAGE: str = (
    "Automated Program Repair platform. To view help on subcommands, run with "
    'the subcommand "help".'
)

_default_command_name: str = "help"


def _init_args(parser: argparse.ArgumentParser) -> None:
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
    # Parse args to get verbose level before Pydantic CLI parsing
    args, _ = parser.parse_known_args()
    verbose_level: int = min(args.verbose, 3) if hasattr(args, "verbose") else 0
    # Create CLI settings source
    cli_settings: CliSettingsSource = CliSettingsSource(Config, root_parser=parser)

    # Get config file path from environment variable
    config_file_path: str | None = os.getenv("ESBMCAI_CONFIG_FILE")

    # Create settings sources in the desired hierarchy:
    # CLI args -> config file -> environment variables -> .env file -> defaults
    settings_sources: list[PydanticBaseSettingsSource] = []

    # Add config file source if specified
    if config_file_path:
        config_file: Path = Path(config_file_path).expanduser()
        if config_file.exists():
            settings_sources.append(TomlConfigSettingsSource(Config, config_file))

    # Add environment variables source
    settings_sources.append(EnvSettingsSource(Config))

    # Add .env file source
    settings_sources.append(DotEnvSettingsSource(Config, env_file=".env"))

    # Use CliApp.run with custom settings sources
    config = CliApp.run(
        Config, cli_settings_source=cli_settings, settings_sources=settings_sources
    )

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
    component_manager.load_component_config(esbmc)

    # Init built-in commands - Loads everything in the esbmc_ai.commands module.
    commands: list[ChatCommand] = []
    for cmd_classname in getattr(esbmc_ai.commands, "__all__"):
        cmd_type: type = getattr(esbmc_ai.commands, cmd_classname)
        assert issubclass(cmd_type, ChatCommand), f"{cmd_type} is not a ChatCommand"
        cmd: object = cmd_type.create()
        assert isinstance(cmd, ChatCommand)
        cmd.global_config = Config()
        # Load component-specific configuration
        component_manager.load_component_config(cmd)
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
        description=HELP_MESSAGE,
        epilog=f"Made by {__author__}",
    )

    _init_args(parser=parser)

    config: Config
    config = _load_config(parser=parser)
    # Set the config singleton
    Config.set_singleton(config)
    config: Config = Config()

    print(f"ESBMC-AI {__version__}")
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
        result: CommandResult | None = command.execute(kwargs=vars(config))
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
