#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import sys

import readline
import argparse
from typing import Any

from structlog import get_logger
from structlog.stdlib import BoundLogger

from esbmc_ai import Config, ChatCommand, __author__, __version__
from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.command_result import CommandResult
from esbmc_ai.log_utils import LogCategories
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.esbmc import ESBMC
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.command_runner import CommandRunner
import esbmc_ai.commands

# Enables arrow key functionality for input(). Do not remove import.
_ = readline

HELP_MESSAGE: str = (
    "Automated Program Repair platform. To view help on subcommands, run with "
    'the subcommand "help".'
)


def _init_builtin_defaults() -> None:
    # Built-in verifiers
    esbmc = ESBMC.create()
    assert isinstance(esbmc, BaseSourceVerifier)
    VerifierRunner().add_verifier(esbmc)
    # Init built-in commands
    commands: list[ChatCommand] = []
    for cmd_classname in getattr(esbmc_ai.commands, "__all__"):
        cmd_type: type = getattr(esbmc_ai.commands, cmd_classname)
        assert issubclass(cmd_type, ChatCommand), f"{cmd_type} is not a ChatCommand"
        cmd: object = cmd_type.create()
        assert isinstance(cmd, ChatCommand)
        commands.append(cmd)
    CommandRunner(
        builtin_commands=commands,
    )


def _run_command_mode(command: ChatCommand, args: argparse.Namespace) -> None:
    result: CommandResult | None = command.execute()
    if result:
        print(result)
    sys.exit(0)


def _init_args(
    parser: argparse.ArgumentParser,
    map_field_names: dict[str, list[str]],
    ignore_fields: dict[str, list[str]],
) -> None:
    """Initializes the Config's ConfigFields to be accepted by the argument
    parser, this allows all ConfigFields to be loaded as arguments. The Config
    will then use the map_field_names to automatically pre-load values before
    loading the rest of the config.

    Args:
        * parser: The parser to add the arguments into.
        * map_field_names: The parser will map the config fields to use
        alternative names.
        * ignore_fields: Dictionary of field names to not encode automatically.
        This takes precedence over map_fields. The field that matches the key
        in this dictionary will not be mapped. It is a dictionary because they
        can optionally be manually initialized and mapped in the Config, so it
        is worth keeping track of the aliases."""

    parser.add_argument(
        "command",
        type=str,
        nargs="?",
        default="userchat",
        help=(
            "The command to run using the program. To see addon commands "
            "available: Run with 'help' as the default command."
        ),
    )

    parser.add_argument(
        *ignore_fields["solution.filenames"],
        default=[],
        type=str,
        # nargs=argparse.REMAINDER,
        nargs=argparse.ZERO_OR_MORE,
        help="The filename(s) to pass to the verifier.",
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

    # Init arg groups
    arg_groups: dict[str, argparse._ArgumentGroup] = {}
    for f in Config().get_config_fields():
        name_split: list[str] = f.name.split(".")
        if len(name_split) == 1:
            continue  # No group
        arg_groups[name_split[0]] = parser.add_argument_group(
            title=name_split[0],
        )

    for f in Config().get_config_fields():
        if f.name in ignore_fields:
            continue

        # Get either the general parser or a group parser
        arg_parser: argparse._ArgumentGroup | argparse.ArgumentParser = parser
        name_split: list[str] = f.name.split(".")
        if len(name_split) > 1:
            arg_parser = arg_groups[name_split[0]]

        # Get the name that will be shown.
        mappings: list[str] = (
            map_field_names[f.name] if f.name in map_field_names else [f.name]
        )
        # Add single or double dash. Change _ into -, argparse will automatically
        # convert into _ anyway.
        mappings = [
            f"-{m}" if len(m) == 1 else f"--{m.replace("_", "-")}" for m in mappings
        ]

        action: Any
        match f.default_value:
            case str():
                action = "store"
            case bool():
                action = "store_true"
            case _:
                action = "store"

        # Set type
        try:
            # Type is only accepted when the action is not some specific values.
            kwargs = {}
            if action not in (
                "store_true",
                "store_false",
                "append_const",
                "count",
                "help",
                "version",
            ):
                # If None then it will only accept None values so basically useless
                kwargs["type"] = (
                    str if f.default_value is None else type(f.default_value)
                )

            # Create the argument.
            arg_parser.add_argument(
                *mappings,
                action=action,
                required=False,
                # Will not show up in the Namespace
                default=argparse.SUPPRESS,
                help=f.help_message,
                **kwargs,
            )
        except TypeError as e:
            get_logger().critical(f"Failed to encode config into args: {f.name}")
            raise e


def main() -> None:
    """Entry point function"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="ESBMC-AI",
        description=HELP_MESSAGE,
        epilog=f"Made by {__author__}",
    )

    arg_mappings: dict[str, list[str]] = {
        "solution.entry_function": ["entry-function"],
        "ai_model": ["m", "ai-model"],
        "solution.output_dir": ["o", "output-dir"],
        "log.output": ["log-output"],
        "log.by_cat": ["log-by-cat"],
        "log.by_name": ["log-by-name"],
    }

    manual_mappings: dict[str, list[str]] = {
        "solution.filenames": ["filenames"],
        "ai_custom": ["ai_custom"],  # Block
    }

    _init_args(
        parser=parser,
        map_field_names=arg_mappings,
        ignore_fields=manual_mappings,
    )

    args: argparse.Namespace = parser.parse_args()

    print(f"ESBMC-AI {__version__}")
    print(f"Made by {__author__}")
    print()

    Config().load(args, arg_mappings | manual_mappings)
    print(f"Config File: {Config().get_value("ESBMCAI_CONFIG_FILE")}")

    _init_builtin_defaults()
    logger: BoundLogger = get_logger().bind(category=LogCategories.SYSTEM)

    if Config().get_value("dev_mode"):
        logger.warn("Development Mode Activated")

    # Load addons
    AddonLoader(Config())
    # Bind addons to command runner and verifier runner.
    CommandRunner().addon_commands.update(AddonLoader().chat_command_addons)
    VerifierRunner()._verifiers = (
        VerifierRunner()._verifiers | AddonLoader().verifier_addons
    )
    # Set verifier to use
    VerifierRunner().set_verifier_by_name(Config().get_value("verifier.name"))

    # Run the command
    command = args.command
    command_names: list[str] = CommandRunner().command_names
    if command in command_names:
        print("Running Command:", command, "\n")
        _run_command_mode(command=CommandRunner().commands[command], args=args)
        sys.exit(0)
    else:
        logger.error(
            f"Error: Unknown command: {command}. Choose from: "
            + ", ".join(command_names)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
