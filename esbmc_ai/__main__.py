#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import sys

import readline
import argparse

from structlog import get_logger
from structlog.stdlib import BoundLogger

from esbmc_ai import Config, ChatCommand, __author__, __version__
from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.command_result import CommandResult
from esbmc_ai.log_utils import Categories
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.esbmc import ESBMC
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.command_runner import CommandRunner
import esbmc_ai.commands

# Enables arrow key functionality for input(). Do not remove import.
_ = readline

HELP_MESSAGE: str = """Automated Program Repair platform. To view additional help
run with the subcommand "help"."""


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


def main() -> None:
    """Entry point function"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="ESBMC-AI",
        description=HELP_MESSAGE,
        epilog=f"Made by {__author__}",
    )

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
        "filenames",
        default=[],
        type=str,
        nargs=argparse.REMAINDER,
        help="The filename(s) to pass to the verifier.",
    )

    parser.add_argument(
        "--entry-function",
        action="store",
        default="main",
        type=str,
        required=False,
        help="The name of the entry function to repair, defaults to main.",
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

    parser.add_argument(
        "-m",
        "--ai-model",
        default="",
        help=(
            "Which AI model to use. Specify any OpenAI model, Anthropic model, "
            "or custom defined model."
        ),
    )

    parser.add_argument(
        "-r",
        "--raw-conversation",
        action="store_true",
        default=False,
        help="Show the raw conversation at the end of a command. Good for debugging...",
    )

    parser.add_argument(
        "-p",
        "--generate-patches",
        action="store_true",
        default=False,
        help="Generate patch files and place them in the same folder as the source files.",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        default="",
        help="Store the result at the following dir. Specifying the same directory will "
        + "overwrite the original file.",
    )

    args: argparse.Namespace = parser.parse_args()

    print(f"ESBMC-AI {__version__}")
    print(f"Made by {__author__}")
    print()

    Config().load(args)
    print(f"Config File: {Config().get_value("ESBMCAI_CONFIG_FILE")}")

    _init_builtin_defaults()
    logger: BoundLogger = get_logger().bind(category=Categories.SYSTEM)

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
