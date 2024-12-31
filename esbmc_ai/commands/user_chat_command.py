# Author: Yiannis Charalambous

import sys
from typing import Any, Optional, override

from langchain_core.language_models import BaseChatModel
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.chats.user_chat import UserChat
from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.commands.chat_command import ChatCommand
from esbmc_ai.commands.command_result import CommandResult
from esbmc_ai.commands.fix_code_command import FixCodeCommand, FixCodeCommandResult
from esbmc_ai.config import Config
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.logging import print_horizontal_line, printv, printvv
from esbmc_ai.solution import SourceFile, get_solution
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.verifiers.base_source_verifier import VerifierOutput

"""This module contains the User Chat Command which is the default command that
is executed when no command is specified. It acts as a command line interface
for running the program."""


class UserChatCommand(ChatCommand):
    """The user chat command is the default command that is executed when no
    other command is specified. It runs with execute and exits the entire program
    when the command is finished. It is used to launch other commands."""

    def __init__(
        self,
        command_runner: CommandRunner,
        verifier_runner: VerifierRunner,
        fix_code_command: FixCodeCommand,
    ) -> None:
        super().__init__("userchat", "Ran automatically and not exposed to the system.")

        self.command_runner: CommandRunner = command_runner
        self.verifier_runner: VerifierRunner = verifier_runner
        self.fix_code_command: FixCodeCommand = fix_code_command

        self.anim: BaseLoadingWidget = (
            LoadingWidget()
            if Config().get_value("loading_hints")
            else BaseLoadingWidget()
        )

    def _run_esbmc(self, source_file: SourceFile, anim: BaseLoadingWidget) -> str:
        assert source_file.file_path

        with anim("Verifier is processing... Please Wait"):
            verifier_result: VerifierOutput = (
                self.verifier_runner.verifier.verify_source(
                    source_file=source_file,
                    esbmc_params=Config().get_value("verifier.esbmc.params"),
                    timeout=Config().get_value("verifier.esbmc.timeout"),
                )
            )

        # ESBMC will output 0 for verification success and 1 for verification
        # failed, if anything else gets thrown, it's an ESBMC error.
        if not Config().get_value("allow_successful") and verifier_result.successful():
            printv(f"Verifier exit code: {verifier_result.return_code}")
            printv(f"Verifier Output:\n\n{verifier_result.output}")
            print("Sample successfuly verified. Exiting...")
            sys.exit(0)

        return verifier_result.output

    def init_commands(self) -> None:
        """# Bus Signals
        Function that handles initializing commands. Each command needs to be added
        into the commands array in order for the command to register to be called by
        the user and also register in the help system."""

        # Let the AI model know about the corrected code.
        self.fix_code_command.on_solution_signal.add_listener(self.chat.set_solution)
        self.fix_code_command.on_solution_signal.add_listener(
            lambda source_code: get_solution()
            .files[0]
            .update_content(content=source_code, reset_changes=True)
        )

    def print_assistant_response(
        self,
        response: ChatResponse,
        hide_stats: bool = False,
    ) -> None:
        print(f"{response.message.type}: {response.message.content}\n\n")

        if not hide_stats:
            print(
                "Stats:",
                f"total tokens: {response.total_tokens},",
                f"max tokens: {self.chat.ai_model.tokens}",
                f"finish reason: {response.finish_reason}",
            )

    @staticmethod
    def _execute_fix_code_command_one_file(
        fix_code_command: FixCodeCommand,
        source_file: SourceFile,
        anim: Optional[BaseLoadingWidget] = None,
    ) -> FixCodeCommandResult:
        """Shortcut method to execute fix code command."""
        return fix_code_command.execute(
            anim=anim,
            ai_model=Config().get_ai_model(),
            source_file=source_file,
            generate_patches=Config().generate_patches,
            message_history=Config().get_value("fix_code.message_history"),
            api_keys=Config().api_keys,
            temperature=Config().get_value("fix_code.temperature"),
            max_attempts=Config().get_value("fix_code.max_attempts"),
            requests_max_tries=Config().get_llm_requests_max_tries(),
            requests_timeout=Config().get_llm_requests_timeout(),
            esbmc_params=Config().get_value("verifier.esbmc.params"),
            raw_conversation=Config().raw_conversation,
            temp_auto_clean=Config().get_value("temp_auto_clean"),
            verifier_timeout=Config().get_value("verifier.esbmc.timeout"),
            source_code_format=Config().get_value("source_code_format"),
            esbmc_output_format=Config().get_value("verifier.esbmc.output_type"),
            scenarios=Config().get_fix_code_scenarios(),
            temp_file_dir=Config().get_value("temp_file_dir"),
            output_dir=Config().output_dir,
        )

    @override
    def execute(self, **kwargs: Optional[Any]) -> Optional[CommandResult]:
        # Read the source code and esbmc output.
        print("Reading source code...")
        get_solution().load_source_files(Config().filenames)
        print(f"Running ESBMC with {Config().get_value('verifier.esbmc.params')}\n")
        source_file: SourceFile = get_solution().files[0]

        esbmc_output: str = self._run_esbmc(source_file, self.anim)

        # Print verbose lvl 2
        print_horizontal_line(2)
        printvv(esbmc_output)
        print_horizontal_line(2)

        source_file.assign_verifier_output(esbmc_output)
        del esbmc_output

        printv(f"Initializing the LLM: {Config().get_ai_model().name}\n")
        chat_llm: BaseChatModel = (
            Config()
            .get_ai_model()
            .create_llm(
                api_keys=Config().api_keys,
                temperature=Config().get_value("user_chat.temperature"),
                requests_max_tries=Config().get_value("llm_requests.max_tries"),
                requests_timeout=Config().get_value("llm_requests.timeout"),
            )
        )

        printv("Creating user chat")
        self.chat: UserChat = UserChat(
            ai_model=Config().get_ai_model(),
            llm=chat_llm,
            verifier=self.verifier_runner.verifier,
            source_code=source_file.latest_content,
            esbmc_output=source_file.latest_verifier_output,
            system_messages=Config().get_user_chat_system_messages(),
            set_solution_messages=Config().get_user_chat_set_solution(),
        )

        printv("Initializing commands...")
        self.init_commands()

        # Show the initial output.
        response: ChatResponse
        if len(str(Config().get_user_chat_initial().content)) > 0:
            printv("Using initial prompt from file...\n")
            with self.anim("Model is parsing ESBMC output... Please Wait"):
                try:
                    response = self.chat.send_message(
                        message=str(Config().get_user_chat_initial().content),
                    )
                except Exception as e:
                    print("There was an error while generating a response: {e}")
                    sys.exit(1)

            if response.finish_reason == FinishReason.length:
                raise RuntimeError(
                    f"The token length is too large: {self.chat.ai_model.tokens}"
                )
        else:
            raise RuntimeError("User mode initial prompt not found in config.")

        self.print_assistant_response(response)
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
                if command == self.fix_code_command.command_name:
                    # Fix Code command
                    print()
                    print("ESBMC-AI will generate a fix for the code...")

                    result: FixCodeCommandResult = (
                        self._execute_fix_code_command_one_file(
                            fix_code_command=self.fix_code_command,
                            source_file=source_file,
                        )
                    )

                    if result.successful:
                        print(
                            "\n\nESBMC-AI: Here is the corrected code, verified with ESBMC:"
                        )
                        print(f"```\n{result.repaired_source}\n```")
                    continue
                else:
                    # Commands without parameters or returns are handled automatically.
                    if command in self.command_runner.commands:
                        self.command_runner.commands[command].execute()
                        break
                    else:
                        print("Error: Unknown command...")
                    continue
            elif user_message == "":
                continue
            else:
                print()

            # User chat mode send and process current message response.
            while True:
                # Send user message to AI model and process.
                with self.anim("Generating response... Please Wait"):
                    response = self.chat.send_message(user_message)

                if response.finish_reason == FinishReason.stop:
                    break
                elif response.finish_reason == FinishReason.length:
                    with self.anim(
                        "Message stack limit reached. Shortening message stack... Please Wait"
                    ):
                        self.chat.compress_message_stack()
                    continue
                else:
                    raise NotImplementedError(
                        f"User Chat Mode: Finish Reason: {response.finish_reason}"
                    )

            self.print_assistant_response(response)
