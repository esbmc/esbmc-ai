#!/usr/bin/env python3

# Author: Yiannis Charalambous 2023

import os
from time import sleep

import argparse
import openai
from subprocess import Popen, PIPE

from src.loading_widget import LoadingWidget
import src.config as config
from src.config import printv
from src.chat import ChatInterface, SYSTEM_MSG_DEFAULT
from src.solution_generator import SolutionGenerator

HELP_MESSAGE: str = """Tool that passes ESBMC output into ChatGPT and allows for natural language
explanations. Type /help in order to view available commands."""

DEFAULT_PROMPT: str = "Walk me through the source code, while also explaining the output of ESBMC at the relevant parts. You shall not start the reply with an acknowledgement message such as 'Certainly'."

# TODO Need to include this in help message, problem is that argparse removes
# the new lines.
ESBMC_HELP: str = """Property checking:
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


def print_help() -> None:
    print()
    print("Commands:")
    print("/help: Print this help message.")
    print("/exit: Exit the program.")
    print(
        "/fix-code: Generates a solution for this code, and reevaluates it with ESBMC."
    )
    print()
    print("Useful AI Questions:")
    print("1) How can I correct this code?")
    print("2) Show me the corrected code.")
    # TODO This needs to be uncommented as soon as ESBMC-AI can detect this query
    # and trigger ESBMC to verify the code.
    # print("3) Can you verify this corrected code with ESBMC again?")
    print()


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


def esbmc(path: str, esbmc_params: list = config.esbmc_params):
    # Build parameters
    esbmc_cmd = [config.esbmc_path]
    esbmc_cmd.extend(esbmc_params)
    esbmc_cmd.append(path)

    # Run ESBMC and get output
    process = Popen(esbmc_cmd, stdout=PIPE)
    (output_bytes, err_bytes) = process.communicate()
    # Return
    exit_code = process.wait()
    output: str = str(output_bytes).replace("\\n", "\n")
    err: str = str(err_bytes).replace("\\n", "\n")
    return exit_code, output, err


def esbmc_load_source_code(
    source_code: str,
    esbmc_params: list = config.esbmc_params,
    auto_clean: bool = True,
):
    # Make temp folder
    if not os.path.exists("temp"):
        os.mkdir("temp")

    # Save to temporary folder.
    with open("temp/tempfile.c", "w") as file:
        file.write(source_code)

    # Call ESBMC to temporary folder.
    results = esbmc("temp/tempfile.c", esbmc_params)

    # Delete temporary file.
    if auto_clean:
        os.remove("temp/tempfile.c")

    # Return
    return results


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


def build_system_messages(source_code: str, esbmc_output: str) -> list:
    """Build the setup messages from either the provided default settings or from
    the loaded files."""
    printv("Loading system messages")
    system_messages: list = []
    if len(config.chat_prompt_user_mode.system_messages) > 0:
        system_messages.extend(config.chat_prompt_user_mode.system_messages)
    else:
        system_messages.extend(SYSTEM_MSG_DEFAULT)

    # Add the introduction of code prompts. TODO Make these loaded from config
    # too in the future.
    system_messages.extend(
        [
            {
                "role": "system",
                "content": f"Reply OK if you understand that the following text is the program source code: {source_code}",
            },
            {"role": "assistant", "content": "OK"},
            {
                "role": "system",
                "content": f"Reply OK if you understand that the following text is the output from ESBMC after reading the program source code: {esbmc_output}",
            },
            {"role": "assistant", "content": "OK"},
        ]
    )

    return system_messages


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ESBMC-ChatGPT",
        description=HELP_MESSAGE,
        epilog="Made by Yiannis Charalambous",
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
        printv("Using default initial prompts...\n")
        anim.start("Model is parsing ESBMC output... Please Wait")
        response = chat.send_message(DEFAULT_PROMPT)
        anim.stop()

    print_assistant_response(chat, response, config.raw_responses)
    print(
        "ESBMC-AI: Type '/help' to view the available in-chat commands, along",
        "with useful prompts to ask the AI model...",
    )

    while True:
        user_message = input(">: ")
        if user_message == "/exit":
            print("exiting...")
            exit(0)
        elif user_message == "/help":
            print_help()
            continue
        elif user_message == "/fix-code":
            print("ESBMC-AI will generate a fix for the code...")
            print("Warning: This is very experimental and will most likely fail...")

            solution_generator = SolutionGenerator(
                system_messages=config.chat_prompt_generator_mode.system_messages,
                initial_prompt=config.chat_prompt_generator_mode.initial_prompt,
                source_code=source_code,
                esbmc_output=esbmc_output,
                model=config.ai_model,
                # TODO Make this loadable from config file.
                temperature=1.6,
            )

            max_retries: int = 10
            for idx in range(max_retries):
                # Generate AI solution
                anim.start("Generating Solution... Please Wait")
                response = solution_generator.generate_solution()
                anim.stop()

                # Pass to ESBMC, a workaround is used where the file is saved
                # to a temporary location since ESBMC needs it in file format.
                anim.start("Verifying with ESBMC... Please Wait")
                exit_code, esbmc_output, esbmc_err = esbmc_load_source_code(
                    str(response),
                    config.esbmc_params,
                    False,
                )
                anim.stop()

                if exit_code == 0:
                    print(
                        "\n\nassistant: Here is the corrected code, verified with ESBMC:"
                    )
                    print(f"```\n{response}\n```")

                    # Let the AI model know about the corrected code.
                    chat.push_to_message_stack(
                        "user",
                        f"Here is the corrected code:\n\n{response}",
                    )
                    chat.push_to_message_stack("assistant", "Understood.")
                    break
                elif exit_code != 1:
                    print(
                        "Error: AI model has probably output text in the source code..."
                    )
                    print(f"ESBMC Error: {esbmc_output}")
                    exit(5)

                # Failure case
                print(f"Failure {idx+1}/{max_retries}: Retrying...")
                anim.start(
                    f"Sleeping {config.consecutive_prompt_delay} seconds due to rate limit..."
                )
                sleep(config.consecutive_prompt_delay)
                anim.stop()
            continue
        elif user_message.startswith("/"):
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
