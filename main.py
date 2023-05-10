#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import os

# Enables arrow key functionality for input(). Do not remove import.
import readline

import argparse
import openai

import src.config as config

from src.commands.chat_command import ChatCommand
from src.commands.fix_code_command import FixCodeCommand
from src.commands.help_command import HelpCommand
from src.commands.exit_command import ExitCommand
from src.commands.verify_code_command import VerifyCodeCommand

from src.loading_widget import LoadingWidget
from src.chat import ChatInterface
from src.logging import printv
from src.esbmc import esbmc


commands: list[ChatCommand] = []
help_command: HelpCommand = HelpCommand()
fix_code_command: FixCodeCommand = FixCodeCommand()
verify_code_command: VerifyCodeCommand = VerifyCodeCommand()
exit_command: ExitCommand = ExitCommand()

chat: ChatInterface

HELP_MESSAGE: str = """Tool that passes ESBMC output into ChatGPT and allows for natural language
explanations. Type /help in order to view available commands."""

ESBMC_HELP: str = """Additional ESBMC Arguments - The following are useful
arguments that can be added after the filename to modify ESBMC functionality.
For all the options, run ESBMC with -h as a parameter:

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


def init_check_health(verbose: bool) -> None:
    def printv(m) -> None:
        if verbose:
            print(m)

    printv("Performing init health check...")
    # Check that the .env file exists.
    if os.path.exists(".env"):
        printv("Environment file has been located")
    else:
        print("Error: .env file is not found in project directory")
        exit(3)


def check_health() -> None:
    printv("Performing health check...")
    # Check that ESBMC exists.
    if os.path.exists(config.esbmc_path):
        printv("ESBMC has been located")
    else:
        print(f"Error: ESBMC could not be found in {config.esbmc_path}")
        exit(3)


def get_src(path: str) -> str:
    with open(path, mode="r") as file:
        content = file.read()
        return str(content)


def print_assistant_response(
    chat: ChatInterface,
    response,
    raw_responses: bool = False,
    hide_stats: bool = False,
) -> None:
    if raw_responses:
        print(response)
        return

    response_role = response.choices[0].message.role
    response_message = response.choices[0].message.content
    print(f"{response_role}: {response_message}\n\n")

    total_tokens: int = response.usage.total_tokens
    max_tokens: int = chat.max_tokens
    finish_reason: str = response.choices[0].finish_reason
    if not hide_stats:
        print(
            "Stats:",
            f"total tokens: {total_tokens},",
            f"max tokens: {max_tokens}",
            f"finish reason: {finish_reason}",
        )


def init_commands() -> None:
    """Function that handles initializing commands. Each command needs to be added
    into the commands array in order for the command to register to be called by
    the user and also register in the help system."""
    # Bus Signals:
    # fix_code_command.on_solution_signal.add_listener(chat.set_solution)
    # fix_code_command.on_solution_signal.add_listener(verify_code_command.set_solution)

    # Setup Help command and commands list.
    global help_command
    commands.extend(
        [
            help_command,
            exit_command,
            fix_code_command,
            verify_code_command,
        ]
    )
    help_command.set_commands(commands)


def build_system_messages(source_code: str, esbmc_output: str) -> list:
    """Build the setup messages from either the provided default settings or from
    the loaded files."""
    printv("Loading system messages")
    system_messages: list = []
    if len(config.chat_prompt_user_mode.system_messages) > 0:
        system_messages.extend(config.chat_prompt_user_mode.system_messages)
    else:
        raise RuntimeError("Chat mode system messages could not be loaded from config.")

    # Add the introduction of code prompts. TODO Make these loaded from config
    # too in the future.
    system_messages.extend(
        [
            {
                "role": "system",
                "content": f"Reply OK if you understand that the following text is the program source code:\n\n{source_code}",
            },
            {"role": "assistant", "content": "OK"},
            {
                "role": "system",
                "content": f"Reply OK if you understand that the following text is the output from ESBMC:\n\n{esbmc_output}",
            },
            {"role": "assistant", "content": "OK"},
        ]
    )

    return system_messages


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ESBMC-ChatGPT",
        description=HELP_MESSAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Made by Yiannis Charalambous\n\n{ESBMC_HELP}",
    )

    parser.add_argument("filename", help="The filename to pass to esbmc.")
    parser.add_argument(
        "remaining",
        nargs=argparse.REMAINDER,
        help="Any arguments after the filename will be passed to ESBMC as parameters.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Output will be verbose.",
    )

    parser.add_argument(
        "-r",
        "--raw-output",
        action="store_true",
        default=False,
        help="Responses from AI model will be shown raw.",
    )

    parser.add_argument(
        "-m",
        "--ai-model",
        default="",
        help="Which AI model to use.",
    )

    parser.add_argument(
        "-a",
        "--append",
        action="store_true",
        default=False,
        help="Any ESBMC parameters passed after the file name will be appended to the ones set in the config file, or the default ones if config file options are not set.",
    )

    args = parser.parse_args()

    print("ESBMC-AI")
    print()

    init_check_health(args.verbose)

    config.load_envs()
    config.load_config(config.cfg_path)
    config.load_args(args)

    check_health()

    anim: LoadingWidget = LoadingWidget()

    # Read the source code and esbmc output.
    printv("Reading source code...")
    printv(f"Running ESBMC with {config.esbmc_params}")
    source_code: str = get_src(args.filename)

    anim.start("ESBMC is processing... Please Wait")
    exit_code, esbmc_output, esbmc_err = esbmc(args.filename)
    anim.stop()

    # ESBMC will output 0 for verification success and 1 for verification
    # failed, if anything else gets thrown, it's an ESBMC error.
    if exit_code == 0:
        print("Success!")
        print(esbmc_output)
        exit(0)
    elif exit_code != 1:
        print(f"ESBMC exit code: {exit_code}")
        exit(1)

    # Prepare the chat.
    printv("Initializing OpenAI")
    openai.api_key = config.openai_api_key

    # Inject output for ai.
    system_messages: list = build_system_messages(source_code, esbmc_output)

    global chat
    chat = ChatInterface(
        system_messages=system_messages,
        model=config.ai_model,
        temperature=config.chat_temperature,
    )
    printv(f"Using AI Model: {chat.model_name}")

    # Show the initial output.
    response = {}
    if len(config.chat_prompt_user_mode.initial_prompt) > 0:
        printv("Using initial prompt from file...\n")
        anim.start("Model is parsing ESBMC output... Please Wait")
        response = chat.send_message(config.chat_prompt_user_mode.initial_prompt)
        anim.stop()
    else:
        raise RuntimeError("User mode initial prompt not found in config.")

    print_assistant_response(chat, response, config.raw_responses)
    print(
        "ESBMC-AI: Type '/help' to view the available in-chat commands, along",
        "with useful prompts to ask the AI model...",
    )

    printv("Initializing commands...")
    init_commands()

    while True:
        # Get user input.
        user_message = input(">: ")

        # Check if it is a command, if not, then pass it to the chat interface.
        if user_message.startswith("/"):
            command: str = user_message[1:]
            if command == fix_code_command.command_name:
                print()
                print("ESBMC-AI will generate a fix for the code...")
                print("Warning: This is very experimental and will most likely fail...")
                error, solution = fix_code_command.execute(
                    source_code=source_code,
                    esbmc_output=esbmc_output,
                )

                if not error:
                    # Let the AI model know about the corrected code.
                    printv("Informing Chat AI about correct code...")
                    chat.set_solution(solution)
                continue
            else:
                # Commands without parameters or returns are handled automatically.
                for cmd in commands:
                    if cmd.command_name == command:
                        cmd.execute()
                        break
                print("Error: Unknown command...")
                continue
        elif user_message == "":
            continue
        else:
            print()

        # Send user message to AI model and process.
        anim.start("Generating response... Please Wait")
        response = chat.send_message(user_message)
        anim.stop()

        print_assistant_response(
            chat,
            response,
            config.raw_responses,
        )


if __name__ == "__main__":
    main()
