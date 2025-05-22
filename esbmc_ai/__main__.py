#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

from pathlib import Path
import sys

import readline
import argparse

from esbmc_ai import Config, ChatCommand, __author__, __version__
from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.command_result import CommandResult
from esbmc_ai.commands.user_chat_command import UserChatCommand
from esbmc_ai.verifiers.esbmc import ESBMC
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.commands import (
    FixCodeCommand,
    HelpCommand,
    ListModelsCommand,
    HelpConfigCommand,
    ExitCommand,
)
from esbmc_ai.logging import printv, printvv, set_default_label

# Enables arrow key functionality for input(). Do not remove import.
_ = readline

# Built-in verifiers
VerifierRunner().add_verifier(ESBMC())
VerifierRunner().set_verifier_by_name("esbmc")
# Init built-in commands
CommandRunner(
    builtin_commands=[
        HelpCommand(),
        HelpConfigCommand(),
        ListModelsCommand(),
        ExitCommand(),
        FixCodeCommand(),
        UserChatCommand(),
    ]
)

HELP_MESSAGE: str = """Automated Program Repair platform. To view additional help
run with the subcommand "help"."""


def _check_health() -> None:
    printv("Performing health check...")
    # Check that ESBMC exists.
    esbmc_path: Path = Config().get_value("verifier.esbmc.path")
    if esbmc_path.exists():
        printv("ESBMC has been located")
    else:
        print(f"Error: ESBMC could not be found in {esbmc_path}")
        sys.exit(3)

    if Config().get_value("dev_mode"):
        print("Development Mode Activated")


def _run_command_mode(command: ChatCommand, args: argparse.Namespace) -> None:
    set_default_label("ESBMC-AI")
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
        help=(
            "The command to run using the program. Options: {"
            + ", ".join(CommandRunner().builtin_commands_names)
            + "}. To see addon commands available: Run with 'help' as the "
            "default command."
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
    # Default command
    if not args.command:
        args.command = "userchat"

    print(f"ESBMC-AI {__version__}")
    print(f"Made by {__author__}")
    print()

    printvv("Loading config")
    Config().load(args)
    printv(f"Config File: {Config().get_value("ESBMCAI_CONFIG_FILE")}")
    _check_health()

    # Load addons
    printvv("Loading addons")
    AddonLoader(Config())
    # Bind addons to command runner and verifier runner.
    CommandRunner.addon_commands = AddonLoader().chat_command_addons
    VerifierRunner()._verifiers = VerifierRunner()._verifiers | AddonLoader().verifier_addons
    # Set verifier to use
    printvv(f"Verifier: {VerifierRunner().verfifier.verifier_name}")
    VerifierRunner().set_verifier_by_name(Config().get_value("verifier.name"))

    printv(f"Source code format: {Config().get_value('source_code_format')}")
    printv(f"ESBMC output type: {Config().get_value('verifier.esbmc.output_type')}")

    # Run the command
    command = args.command
    command_names: list[str] = CommandRunner().command_names
    if command in command_names:
        print("Running Command:", command, "\n")
        _run_command_mode(command=CommandRunner().commands[command], args=args)
        sys.exit(0)
    else:
        print(
            f"Error: Unknown command: {command}. Choose from: "
            + ", ".join(command_names)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
