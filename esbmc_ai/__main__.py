#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

from pathlib import Path
import sys

# Enables arrow key functionality for input(). Do not remove import.
import readline
import argparse

from esbmc_ai.addon_loader import AddonLoader
from esbmc_ai.commands.user_chat_command import UserChatCommand
from esbmc_ai.solution import Solution
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.verifiers.esbmc import ESBMC
from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.commands.fix_code_command import FixCodeCommandResult
from esbmc_ai import Config
from esbmc_ai import __author__, __version__
from esbmc_ai.commands import (
    ChatCommand,
    FixCodeCommand,
    HelpCommand,
    ExitCommand,
)
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.chats import UserChat
from esbmc_ai.logging import printv, printvv
from esbmc_ai.ai_models import _ai_model_names

_ = readline


help_command: HelpCommand = HelpCommand()
fix_code_command: FixCodeCommand = FixCodeCommand()
exit_command: ExitCommand = ExitCommand()

verifier_runner: VerifierRunner = VerifierRunner().init([ESBMC()])
command_runner: CommandRunner = CommandRunner().init(
    builtin_commands=[
        help_command,
        exit_command,
        fix_code_command,
    ]
)

chat: UserChat

HELP_MESSAGE: str = """Tool that passes ESBMC output into ChatGPT and allows for natural language
explanations. Type /help in order to view available commands."""

ESBMC_HELP: str = """Additional ESBMC Arguments - The following are useful
arguments that can be added after the filename to modify ESBMC functionality.
For all the options, run ESBMC with -h as a parameter:

  --compact-trace                  add trace information to output
  --no-assertions                  ignore assertions
  --no-bounds-check                do not do array bounds check
  --no-div-by-zero-check           do not do division by zero check
  --no-pointer-check               do not do pointer check
  --no-align-check                 do not check pointer alignment
  --no-pointer-relation-check      do not check pointer relations
  --no-unlimited-scanf-check       do not do overflow check for scanf/fscanf
                                   with unlimited character width.
  --nan-check                      check floating-point for NaN
  --memory-leak-check              enable memory leak check
  --overflow-check                 enable arithmetic over- and underflow check
  --ub-shift-check                 enable undefined behaviour check on shift
                                   operations
  --struct-fields-check            enable over-sized read checks for struct
                                   fields
  --deadlock-check                 enable global and local deadlock check with
                                   mutex
  --data-races-check               enable data races check
  --lock-order-check               enable for lock acquisition ordering check
  --atomicity-check                enable atomicity check at visible
                                   assignments
  --stack-limit bits (=-1)         check if stack limit is respected
  --error-label label              check if label is unreachable
  --force-malloc-success           do not check for malloc/new failure
"""


def check_health() -> None:
    printv("Performing health check...")
    # Check that ESBMC exists.
    esbmc_path: Path = Config().get_value("verifier.esbmc.path")
    if esbmc_path.exists():
        printv("ESBMC has been located")
    else:
        print(f"Error: ESBMC could not be found in {esbmc_path}")
        sys.exit(3)


def _run_command_mode(command: ChatCommand, args: argparse.Namespace) -> None:
    match command.command_name:
        # Basic fix mode: Supports only 1 file repair.
        case fix_code_command.command_name:
            print("Reading source code...")
            solution: Solution = Solution(Config().filenames)
            print(f"Running ESBMC with {Config().get_value('verifier.esbmc.params')}\n")

            anim: BaseLoadingWidget = (
                LoadingWidget()
                if Config().get_value("loading_hints")
                else BaseLoadingWidget()
            )
            for source_file in solution.files:
                result: FixCodeCommandResult = (
                    UserChatCommand._execute_fix_code_command_one_file(
                        fix_code_command,
                        source_file,
                        anim=anim,
                    )
                )

                print(result)
        case _:
            command.execute()
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ESBMC-AI",
        description=HELP_MESSAGE,
        # argparse.RawDescriptionHelpFormatter allows the ESBMC_HELP to display
        # properly.
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Made by {__author__}\n\n{ESBMC_HELP}",
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
        "-c",
        "--command",
        help="Runs the program in command mode, it will exit after the command ends with an exit code. Options: {"
        + ", ".join(command_runner.builtin_commands_names)
        + "}. To see addon commands avaiilable: Run with '-c help'.",
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

    printvv("Loading main config")
    Config().init(args)
    printv(f"Config File: {Config().cfg_path}")
    check_health()
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

    # ===========================================
    # Command mode
    # ===========================================
    # Check if command is called and call it.
    # If not, then continue to user mode.
    if args.command is not None:
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

    # ===========================================
    # User Mode (Supports only 1 file)
    # ===========================================

    UserChatCommand(
        command_runner=command_runner,
        verifier_runner=verifier_runner,
        fix_code_command=fix_code_command,
    ).execute()


if __name__ == "__main__":
    main()
