# Author: Yiannis Charalambous

"""This module contains the User Chat Command which is the default command that
is executed when no command is specified. It acts as a command line interface
for running the program."""

from pathlib import Path
import sys
from typing import Any, Optional, override

from langchain_core.language_models import BaseChatModel
from langchain.schema import BaseMessage, HumanMessage
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.config_field import ConfigField
from esbmc_ai.chats.user_chat import UserChat
from esbmc_ai.component_loader import ComponentLoader
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.command_result import CommandResult
from esbmc_ai.commands.fix_code_command import FixCodeCommand, FixCodeCommandResult
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.component_loader import ComponentLoader
from esbmc_ai.solution import Solution
from esbmc_ai.verifiers.base_source_verifier import VerifierOutput
from esbmc_ai.chat_response import list_to_base_messages
from esbmc_ai import prompt_utils


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

        self.fix_code_command: FixCodeCommand
        self.chat: UserChat
        self.solution: Solution
        self.anim: BaseLoadingWidget

    def _run_esbmc(self) -> VerifierOutput:
        with self.anim("Verifier is processing... Please Wait"):
            verifier_result: VerifierOutput = ComponentLoader().verifier.verify_source(
                solution=self.solution,
                params=self.get_config_value("verifier.esbmc.params"),
                timeout=self.get_config_value("verifier.esbmc.timeout"),
            )

        # ESBMC will output 0 for verification success and 1 for verification
        # failed, if anything else gets thrown, it's an ESBMC error.
        if (
            not self.get_config_value("allow_successful")
            and verifier_result.successful()
        ):
            self.logger.info(f"Verifier exit code: {verifier_result.return_code}")
            self.logger.debug(f"Verifier Output:\n\n{verifier_result.output}")
            print("Sample successfuly verified. Exiting...")
            sys.exit(0)

        return verifier_result

    @override
    def get_config_fields(self) -> list[ConfigField]:
        return [
            ConfigField(
                name="user_chat.temperature",
                default_value=1.0,
                validate=lambda v: isinstance(v, float) and 0 <= v <= 2.0,
                error_message="Temperature needs to be a value between 0 and 2.0",
                help_message="The temperature of the LLM for the user chat command.",
            ),
            ConfigField(
                name="user_chat.initial_prompt_template",
                default_value=None,
                validate=lambda v: isinstance(v, str),
                on_load=lambda v: HumanMessage(content=v),
                help_message="The initial prompt for the user chat command.",
            ),
            ConfigField(
                name="user_chat.system_prompt_templates",
                default_value=None,
                validate=prompt_utils.validate_prompt_template_conversation,
                on_load=list_to_base_messages,
                help_message="The system prompt for the user chat command.",
            ),
            ConfigField(
                name="user_chat.set_solution_prompt_templates",
                default_value=None,
                validate=prompt_utils.validate_prompt_template_conversation,
                on_load=list_to_base_messages,
                help_message="The prompt for the user chat command when a solution "
                "is found by the fix code command.",
            ),
        ]

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

    def get_user_chat_initial(self) -> BaseMessage:
        """Value of field: user_chat.initial_prompt_template"""
        return self.get_config_value("user_chat.initial_prompt_template")

    def get_user_chat_system_messages(self) -> list[BaseMessage]:
        """Value of field: user_chat.system_prompt_templates"""
        return self.get_config_value("user_chat.system_prompt_templates")

    def get_user_chat_set_solution(self) -> list[BaseMessage]:
        """Value of field: user_chat.set_solution_prompt_templates"""
        return self.get_config_value("user_chat.set_solution_prompt_templates")

    @override
    def execute(self, **kwargs: Optional[Any]) -> Optional[CommandResult]:
        _ = kwargs

        ComponentLoader().load_base_component_config(self)

        self.anim = (
            LoadingWidget()
            if self.get_config_value("loading_hints")
            else BaseLoadingWidget()
        )

        # Assign fix code command - In the future make this not explicitly mentioned
        # and make the signal bus system available to all commands.
        fix_code_command: Any = ComponentLoader().commands["fix-code"]
        assert isinstance(fix_code_command, FixCodeCommand)
        self.fix_code_command = fix_code_command

        # Read the source code and esbmc output.
        print("Reading source code...")
        file_paths: list[Path] = self.get_config_value("solution.filenames")
        self.solution = Solution(file_paths)
        if len(self.solution.files) == 0:
            print("Error: No files specified.")
            sys.exit(1)

        print(f"Running ESBMC with {self.get_config_value('verifier.esbmc.params')}\n")
        esbmc_output: VerifierOutput = self._run_esbmc()

        self.logger.info(
            f"Initializing the LLM: {self.get_config_value("ai_model").name}\n"
        )
        chat_llm: BaseChatModel = self.get_config_value("ai_model").create_llm(
            temperature=self.get_config_value("user_chat.temperature"),
            requests_max_tries=self.get_config_value("llm_requests.max_tries"),
            requests_timeout=self.get_config_value("llm_requests.timeout"),
        )

        self.logger.info("Creating user chat")
        self.chat = UserChat(
            ai_model=self.get_config_value("ai_model"),
            llm=chat_llm,
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
                command, command_args = ComponentLoader().parse_command(user_message)
                command = command[1:]  # Remove the /
                if command == self.fix_code_command.command_name:
                    # Fix Code command
                    print()
                    print("ESBMC-AI will generate a fix for the code...")

                    result: FixCodeCommandResult = fix_code_command.execute(
                        source_file=self.solution.files[0]
                    )

                    if result.successful:
                        print(
                            "\n\nESBMC-AI: Here is the corrected code, verified with ESBMC:"
                        )
                        print(f"```\n{result.repaired_source}\n```")
                    continue
                else:
                    # Commands without parameters or returns are handled automatically.
                    if command in ComponentLoader().commands:
                        ComponentLoader().commands[command].execute()
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
