#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

from pathlib import Path
import sys

# Enables arrow key functionality for input(). Do not remove import.
import readline

_ = readline

from langchain_core.language_models import BaseChatModel

from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.commands.fix_code_command import FixCodeCommandResult


import argparse

from esbmc_ai import Config
from esbmc_ai import __author__, __version__
from esbmc_ai.solution import SourceFile, Solution, get_solution

from esbmc_ai.commands import (
    ChatCommand,
    FixCodeCommand,
    HelpCommand,
    ExitCommand,
    FixCodeCommandResult,
)

from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.chats import UserChat
from esbmc_ai.logging import print_horizontal_line, printv, printvv
from esbmc_ai.esbmc_util import ESBMCUtil
from esbmc_ai.chat_response import FinishReason, ChatResponse
from esbmc_ai.ai_models import _ai_model_names

help_command: HelpCommand = HelpCommand()
fix_code_command: FixCodeCommand = FixCodeCommand()
exit_command: ExitCommand = ExitCommand()
command_runner: CommandRunner = CommandRunner(
    [
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
    esbmc_path: Path = Config.get_value("esbmc.path")
    if esbmc_path.exists():
        printv("ESBMC has been located")
    else:
        print(f"Error: ESBMC could not be found in {esbmc_path}")
        sys.exit(3)


def print_assistant_response(
    chat: UserChat,
    response: ChatResponse,
    hide_stats: bool = False,
) -> None:
    print(f"{response.message.type}: {response.message.content}\n\n")

    if not hide_stats:
        print(
            "Stats:",
            f"total tokens: {response.total_tokens},",
            f"max tokens: {chat.ai_model.tokens}",
            f"finish reason: {response.finish_reason}",
        )


def init_addons() -> None:
    command_runner.addon_commands.clear()
    command_runner.addon_commands.extend(Config.get_value("addon_modules"))
    if len(command_runner.addon_commands):
        printv("Addons:\n\t* " + "\t * ".join(command_runner.addon_commands_names))


def update_solution(source_code: str) -> None:
    get_solution().files[0].update_content(content=source_code, reset_changes=True)


def _run_esbmc(source_file: SourceFile, anim: BaseLoadingWidget) -> str:
    assert source_file.file_path

    with anim("ESBMC is processing... Please Wait"):
        exit_code, esbmc_output = ESBMCUtil.esbmc(
            path=source_file.file_path,
            esbmc_params=Config.get_value("esbmc.params"),
            timeout=Config.get_value("esbmc.timeout"),
        )

    # ESBMC will output 0 for verification success and 1 for verification
    # failed, if anything else gets thrown, it's an ESBMC error.
    if not Config.get_value("allow_successful") and exit_code == 0:
        printv("Success!")
        print(esbmc_output)
        sys.exit(0)
    elif exit_code != 0 and exit_code != 1:
        printv(f"ESBMC exit code: {exit_code}")
        printv(f"ESBMC Output:\n\n{esbmc_output}")
        sys.exit(1)

    return esbmc_output


def init_commands() -> None:
    """# Bus Signals
    Function that handles initializing commands. Each command needs to be added
    into the commands array in order for the command to register to be called by
    the user and also register in the help system."""

    # Let the AI model know about the corrected code.
    fix_code_command.on_solution_signal.add_listener(chat.set_solution)
    fix_code_command.on_solution_signal.add_listener(update_solution)


def _execute_fix_code_command(source_file: SourceFile) -> FixCodeCommandResult:
    """Shortcut method to execute fix code command."""
    return fix_code_command.execute(
        ai_model=Config.get_ai_model(),
        source_file=source_file,
        generate_patches=Config.generate_patches,
        message_history=Config.get_value("fix_code.message_history"),
        api_keys=Config.api_keys,
        temperature=Config.get_value("fix_code.temperature"),
        max_attempts=Config.get_value("fix_code.max_attempts"),
        requests_max_tries=Config.get_llm_requests_max_tries(),
        requests_timeout=Config.get_llm_requests_timeout(),
        esbmc_params=Config.get_value("esbmc.params"),
        raw_conversation=Config.raw_conversation,
        temp_auto_clean=Config.get_value("temp_auto_clean"),
        verifier_timeout=Config.get_value("esbmc.timeout"),
        source_code_format=Config.get_value("source_code_format"),
        esbmc_output_format=Config.get_value("esbmc.output_type"),
        scenarios=Config.get_fix_code_scenarios(),
        temp_file_dir=Config.get_value("temp_file_dir"),
        output_dir=Config.output_dir,
    )


def _run_command_mode(command: ChatCommand, args: argparse.Namespace) -> None:
    path_arg: Path = Path(args.filename)

    anim: BaseLoadingWidget = (
        LoadingWidget() if Config.get_value("loading_hints") else BaseLoadingWidget()
    )

    solution: Solution = get_solution()
    if path_arg.is_dir():
        for path in path_arg.glob("**/*"):
            if path.is_file() and path.name:
                solution.add_source_file(path, None)
    else:
        solution.add_source_file(path_arg, None)

    match command.command_name:
        case fix_code_command.command_name:
            for source_file in solution.files:
                # Run ESBMC first round
                esbmc_output: str = _run_esbmc(source_file, anim)
                source_file.assign_verifier_output(esbmc_output)

                result: FixCodeCommandResult = _execute_fix_code_command(source_file)

                print(result)
        case _:
            command.execute()
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ESBMC-ChatGPT",
        description=HELP_MESSAGE,
        # argparse.RawDescriptionHelpFormatter allows the ESBMC_HELP to display
        # properly.
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Made by {__author__}\n\n{ESBMC_HELP}",
    )

    parser.add_argument(
        "filename",
        help="The filename to pass to esbmc.",
    )

    parser.add_argument(
        "remaining",
        nargs=argparse.REMAINDER,
        help="Any arguments after the filename will be passed to ESBMC as parameters.",
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
        "-a",
        "--append",
        action="store_true",
        default=False,
        help="Any ESBMC parameters passed after the file name will be appended to the ones set in the config file, or the default ones if config file options are not set.",
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

    Config.init(args)
    ESBMCUtil.init(Config.get_value("esbmc.path"))
    check_health()
    init_addons()

    printv(f"Source code format: {Config.get_value('source_code_format')}")
    printv(f"ESBMC output type: {Config.get_value('esbmc.output_type')}")

    anim: BaseLoadingWidget = (
        LoadingWidget() if Config.get_value("loading_hints") else BaseLoadingWidget()
    )

    # Read the source code and esbmc output.
    printv("Reading source code...")
    print(f"Running ESBMC with {Config.get_value('esbmc.params')}\n")

    assert isinstance(args.filename, str)

    # ===========================================
    # Command mode
    # ===========================================
    # Check if command is called and call it.
    # If not, then continue to user mode.
    if args.command != None:
        command = args.command
        command_names: list[str] = command_runner.command_names
        if command in command_names:
            print("Running Command:", command)
            for idx, command_name in enumerate(command_names):
                if command == command_name:
                    _run_command_mode(command=command_runner.commands[idx], args=args)
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

    # Init Solution
    solution: Solution
    # Determine if we are processing one file versus multiple files
    path_arg: Path = Path(args.filename)
    if path_arg.is_dir():
        # Load only files.
        print(
            "Processing multiple files is not supported in User Mode."
            "Call a command using -c to process directories"
        )
        sys.exit(1)
    else:
        # Add the main source file to the solution explorer.
        solution: Solution = get_solution()
        solution.add_source_file(path_arg, None)
    del path_arg

    # Assert that we have one file and one filepath
    assert len(solution.files) == 1

    source_file: SourceFile = solution.files[0]

    esbmc_output: str = _run_esbmc(source_file, anim)

    # Print verbose lvl 2
    print_horizontal_line(2)
    printvv(esbmc_output)
    print_horizontal_line(2)

    source_file.assign_verifier_output(esbmc_output)
    del esbmc_output

    printv(f"Initializing the LLM: {Config.get_ai_model().name}\n")
    chat_llm: BaseChatModel = Config.get_ai_model().create_llm(
        api_keys=Config.api_keys,
        temperature=Config.get_value("user_chat.temperature"),
        requests_max_tries=Config.get_value("llm_requests.max_tries"),
        requests_timeout=Config.get_value("llm_requests.timeout"),
    )

    printv("Creating user chat")
    global chat
    chat = UserChat(
        ai_model=Config.get_ai_model(),
        llm=chat_llm,
        source_code=source_file.latest_content,
        esbmc_output=source_file.latest_verifier_output,
        system_messages=Config.get_user_chat_system_messages(),
        set_solution_messages=Config.get_user_chat_set_solution(),
    )

    printv("Initializing commands...")
    init_commands()

    # Show the initial output.
    response: ChatResponse
    if len(str(Config.get_user_chat_initial().content)) > 0:
        printv("Using initial prompt from file...\n")
        with anim("Model is parsing ESBMC output... Please Wait"):
            response = chat.send_message(
                message=str(Config.get_user_chat_initial().content),
            )

        if response.finish_reason == FinishReason.length:
            raise RuntimeError(f"The token length is too large: {chat.ai_model.tokens}")
    else:
        raise RuntimeError("User mode initial prompt not found in config.")

    print_assistant_response(chat, response)
    print(
        "ESBMC-AI: Type '/help' to view the available in-chat commands, along",
        "with useful prompts to ask the AI model...",
    )

    while True:
        # Get user input.
        user_message = input("user>: ")

        # Check if it is a command, if not, then pass it to the chat interface.
        if user_message.startswith("/"):
            command, command_args = CommandRunner.parse_command(user_message)
            command = command[1:]  # Remove the /
            if command == fix_code_command.command_name:
                # Fix Code command
                print()
                print("ESBMC-AI will generate a fix for the code...")

                result: FixCodeCommandResult = _execute_fix_code_command(source_file)

                if result.successful:
                    print(
                        "\n\nESBMC-AI: Here is the corrected code, verified with ESBMC:"
                    )
                    print(f"```\n{result.repaired_source}\n```")
                continue
            else:
                # Commands without parameters or returns are handled automatically.
                found: bool = False
                for cmd in command_runner.commands:
                    if cmd.command_name == command:
                        found = True
                        cmd.execute()
                        break

                if not found:
                    print("Error: Unknown command...")
                continue
        elif user_message == "":
            continue
        else:
            print()

        # User chat mode send and process current message response.
        while True:
            # Send user message to AI model and process.
            with anim("Generating response... Please Wait"):
                response = chat.send_message(user_message)

            if response.finish_reason == FinishReason.stop:
                break
            elif response.finish_reason == FinishReason.length:
                with anim(
                    "Message stack limit reached. Shortening message stack... Please Wait"
                ):
                    chat.compress_message_stack()
                continue
            else:
                raise NotImplementedError(
                    f"User Chat Mode: Finish Reason: {response.finish_reason}"
                )

        print_assistant_response(
            chat,
            response,
        )


if __name__ == "__main__":
    main()
