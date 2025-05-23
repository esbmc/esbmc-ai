# Author: Yiannis Charalambous

"""This module contains the User Chat Command which is the default command that
is executed when no command is specified. It acts as a command line interface
for running the program."""

from pathlib import Path
import sys
from typing import Any, Optional, override

from langchain_core.language_models import BaseChatModel
from langchain.schema import BaseMessage
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.chats.user_chat import UserChat
from esbmc_ai.command_runner import CommandRunner
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.command_result import CommandResult
from esbmc_ai.commands.fix_code_command import FixCodeCommand, FixCodeCommandResult
from esbmc_ai.config import Config
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.log_utils import print_horizontal_line
from esbmc_ai.solution import Solution
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.verifiers.base_source_verifier import VerifierOutput


class UserChatCommand(ChatCommand):
    """The user chat command is the default command that is executed when no
    other command is specified. It runs with execute and exits the entire program
    when the command is finished. It is used to launch other commands."""

    def __init__(self) -> None:
        super().__init__(
            command_name="userchat",
            help_message=(
                "Allow the user to ask the LLM questions about the "
                "vulnerability. Currently only supports 1 file."
            ),
        )

        self.command_runner: CommandRunner
        self.verifier_runner: VerifierRunner
        self.fix_code_command: FixCodeCommand
        self.chat: UserChat
        self.solution: Solution
        self.anim: BaseLoadingWidget

        self._config = Config()

    def _run_esbmc(self) -> str:
        with self.anim("Verifier is processing... Please Wait"):
            verifier_result: VerifierOutput = (
                self.verifier_runner.verifier.verify_source(
                    solution=self.solution,
                    params=Config().get_value("verifier.esbmc.params"),
                    timeout=Config().get_value("verifier.esbmc.timeout"),
                )
            )

        # ESBMC will output 0 for verification success and 1 for verification
        # failed, if anything else gets thrown, it's an ESBMC error.
        if not Config().get_value("allow_successful") and verifier_result.successful():
            self.logger.info(f"Verifier exit code: {verifier_result.return_code}")
            self.logger.debug(f"Verifier Output:\n\n{verifier_result.output}")
            print("Sample successfuly verified. Exiting...")
            sys.exit(0)

        return verifier_result.output

    def init_commands(self) -> None:
        """# Bus Signals
        Function that handles initializing commands. Each command needs to be added
        into the commands array in order for the command to register to be called by
        the user and also register in the help system."""

        def update_source(solution: Solution, content: str) -> None:
            solution.files[0].content = content

        # Let the AI model know about the corrected code.
        self.fix_code_command.on_solution_signal.add_listener(self.chat.set_solution)
        self.fix_code_command.on_solution_signal.add_listener(
            lambda source_code: update_source(self.solution, source_code)
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
    def get_user_chat_initial() -> BaseMessage:
        """Value of field: prompt_templates.user_chat.initial"""
        return Config().get_value("prompt_templates.user_chat.initial")

    @staticmethod
    def get_user_chat_system_messages() -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.system"""
        return Config().get_value("prompt_templates.user_chat.system")

    @staticmethod
    def get_user_chat_set_solution() -> list[BaseMessage]:
        """Value of field: prompt_templates.user_chat.set_solution"""
        return Config().get_value("prompt_templates.user_chat.set_solution")

    @override
    def execute(self, **kwargs: Optional[Any]) -> Optional[CommandResult]:
        _ = kwargs

        self.command_runner = CommandRunner()
        self.verifier_runner = VerifierRunner()
        self.anim = (
            LoadingWidget()
            if Config().get_value("loading_hints")
            else BaseLoadingWidget()
        )

        # Assign fix code command - In the future make this not explicitly mentioned
        # and make the signal bus system available to all commands.
        assert isinstance(self.command_runner.commands["fix-code"], FixCodeCommand)
        self.fix_code_command = self.command_runner.commands["fix-code"]

        # Read the source code and esbmc output.
        print("Reading source code...")
        file_paths: list[Path] = self.get_config_value("solution.filenames")
        self.solution = Solution(file_paths)
        if len(self.solution.files) == 0:
            print("Error: No files specified.")
            sys.exit(1)

        print(f"Running ESBMC with {Config().get_value('verifier.esbmc.params')}\n")
        esbmc_output: str = self._run_esbmc()

        # Print verbose lvl 2
        print_horizontal_line(2)
        self.logger.debug(esbmc_output)
        print_horizontal_line(2)

        self.logger.info(
            f"Initializing the LLM: {Config().get_value("ai_model").name}\n"
        )
        chat_llm: BaseChatModel = (
            Config()
            .get_value("ai_model")
            .create_llm(
                temperature=Config().get_value("user_chat.temperature"),
                requests_max_tries=Config().get_value("llm_requests.max_tries"),
                requests_timeout=Config().get_value("llm_requests.timeout"),
            )
        )

        self.logger.info("Creating user chat")
        self.chat = UserChat(
            ai_model=Config().get_value("ai_model"),
            llm=chat_llm,
            verifier=self.verifier_runner.verifier,
            solution=self.solution,
            esbmc_output=esbmc_output,
            system_messages=UserChatCommand().get_user_chat_system_messages(),
            set_solution_messages=UserChatCommand().get_user_chat_set_solution(),
        )

        self.logger.info("Initializing commands...")
        self.init_commands()

        # Show the initial output.
        response: ChatResponse
        if len(str(self.get_user_chat_initial().content)) > 0:
            self.logger.info("Using initial prompt from file...\n")
            with self.anim("Model is parsing ESBMC output... Please Wait"):
                try:
                    response = self.chat.send_message(
                        message=str(self.get_user_chat_initial().content),
                    )
                except Exception as e:
                    print(f"There was an error while generating a response: {e}")
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

                    result: FixCodeCommandResult = self.command_runner.commands[
                        "fix-code"
                    ].execute(source_file=self.solution.files[0])

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
                        continue
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
