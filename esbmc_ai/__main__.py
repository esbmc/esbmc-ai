#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

from pathlib import Path
import sys

import readline
import argparse

from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.commands.user_chat_command import UserChatCommand
from esbmc_ai.solution import Solution
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.commands.fix_code_command import FixCodeCommandResult
from esbmc_ai import Config
from esbmc_ai import __author__, __version__
from esbmc_ai.commands import (
    ChatCommand,
    FixCodeCommand,
    HelpCommand,
    ConfigInfoCommand,
    ExitCommand,
)
from esbmc_ai.logging import printv, printvv, set_default_label
from esbmc_ai.ai_models import _ai_model_names

# Enables arrow key functionality for input(). Do not remove import.
_ = readline

# Init built-in commands
help_command: HelpCommand = HelpCommand()
fix_code_command: FixCodeCommand = FixCodeCommand()
exit_command: ExitCommand = ExitCommand()
user_chat_command: UserChatCommand = UserChatCommand()
config_info_command: ConfigInfoCommand = ConfigInfoCommand()

verifier_runner: VerifierRunner = VerifierRunner()
command_runner: CommandRunner = CommandRunner().init(
    builtin_commands=[
        help_command,
        config_info_command,
        exit_command,
        fix_code_command,
        user_chat_command,
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
    match command.command_name:
        case user_chat_command.command_name:
            user_chat_command.execute(
                command_runner=command_runner,
                verifier_runner=verifier_runner,
                fix_code_command=fix_code_command,
            )
        # Basic fix mode: Supports only 1 file repair.
        case fix_code_command.command_name:
            print("Reading source code...")
            solution: Solution = Solution(Config().filenames)
            print(f"Running ESBMC with {Config().get_value('verifier.esbmc.params')}\n")

            for source_file in solution.files:
                result: FixCodeCommandResult = fix_code_command.execute(
                    source_file=source_file
                )

                print(result)
        case _:
            command.execute()
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
        help="The command to run using the program. Options: {"
        + ", ".join(command_runner.builtin_commands_names)
        + "}. To see addon commands available: Run with 'help' as the default command.",
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
        help="Show up to 3 levels of verbose output. Level 1: extra information. Level 2: show failed generations, show ESBMC output. Level 3: print hidden pushes to the message stack.",
    )

    parser.add_argument(
        "-m",
        "--ai-model",
        default="",
        help="Which AI model to use. Built-in models: {OpenAI GPT models, "
        + ", ".join(_ai_model_names)
        + ", +custom models}",
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

    printvv("Loading main config")
    Config().init(args)
    printv(f"Config File: {Config().cfg_path}")
    _check_health()
    # Load addons
    printvv("Loading addons")
    AddonLoader().init(Config(), verifier_runner.builtin_verifier_names)
    # Bind addons to command runner and verifier runner.
    command_runner.addon_commands = AddonLoader().chat_command_addons
    verifier_runner.addon_verifiers = AddonLoader().verifier_addons
    # Set verifier to use
    printvv(f"Verifier: {verifier_runner.verfifier.verifier_name}")
    verifier_runner.set_verifier_by_name(Config().get_value("verifier.name"))

    printv(f"Source code format: {Config().get_value('source_code_format')}")
    printv(f"ESBMC output type: {Config().get_value('verifier.esbmc.output_type')}")

    # Run the command
    command = args.command
    command_names: list[str] = command_runner.command_names
    if command in command_names:
        print("Running Command:", command, "\n")
        _run_command_mode(command=command_runner.commands[command], args=args)
        sys.exit(0)
    else:
        print(
            f"Error: Unknown command: {command}. Choose from: "
            + ", ".join(command_names)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
