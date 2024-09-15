# Author: Yiannis Charalambous

import sys
from typing import Any, Optional, Tuple
from typing_extensions import override

from esbmc_ai.ai_models import AIModel
from esbmc_ai.api_key_collection import APIKeyCollection
from esbmc_ai.chat_response import FinishReason
from esbmc_ai.chats import LatestStateSolutionGenerator, SolutionGenerator
from esbmc_ai.chats.solution_generator import ESBMCTimedOutException
from esbmc_ai.commands.command_result import CommandResult
from esbmc_ai.config import FixCodeScenarios
from esbmc_ai.reverse_order_solution_generator import ReverseOrderSolutionGenerator
from esbmc_ai.solution import SourceFile

from .chat_command import ChatCommand
from ..msg_bus import Signal
from ..loading_widget import create_loading_widget
from ..esbmc_util import ESBMCUtil
from ..logging import print_horizontal_line, printv, printvv


class FixCodeCommandResult(CommandResult):
    def __init__(self, successful: bool, repaired_source: Optional[str] = None) -> None:
        super().__init__()
        self._successful: bool = successful
        self.repaired_source: Optional[str] = repaired_source

    @property
    @override
    def successful(self) -> bool:
        return self._successful

    @override
    def __str__(self) -> str:
        return (
            self.repaired_source
            if self._successful and self.repaired_source != None
            else "ESBMC-AI Notice: Failed all attempts..."
        )


class FixCodeCommand(ChatCommand):
    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim = create_loading_widget()

    @override
    def execute(self, **kwargs: Any) -> FixCodeCommandResult:
        def print_raw_conversation() -> None:
            print_horizontal_line(0)
            print("ESBMC-AI Notice: Printing raw conversation...")
            all_messages = solution_generator._system_messages.copy()
            all_messages.extend(solution_generator.messages.copy())
            messages: list[str] = [f"{msg.type}: {msg.content}" for msg in all_messages]
            print("\n" + "\n\n".join(messages))
            print("ESBMC-AI Notice: End of raw conversation")

        # Handle kwargs
        source_file: SourceFile = kwargs["source_file"]
        assert source_file.file_path

        generate_patches: bool = (
            kwargs["generate_patches"] if "generate_patches" in kwargs else False
        )

        message_history: str = (
            kwargs["message_history"] if "message_history" else "normal"
        )

        api_keys: APIKeyCollection = kwargs["api_keys"]
        ai_model: AIModel = kwargs["ai_model"]
        temperature: float = kwargs["temperature"]
        max_tries: int = kwargs["requests_max_tries"]
        timeout: int = kwargs["requests_timeout"]
        source_code_format: str = kwargs["source_code_format"]
        esbmc_output_format: str = kwargs["esbmc_output_format"]
        scenarios: FixCodeScenarios = kwargs["scenarios"]
        max_attempts: int = kwargs["max_attempts"]
        esbmc_params: list[str] = kwargs["esbmc_params"]
        verifier_timeout: int = kwargs["verifier_timeout"]
        temp_auto_clean: bool = kwargs["temp_auto_clean"]
        raw_conversation: bool = (
            kwargs["raw_conversation"] if "raw_conversation" in kwargs else False
        )
        # End of handle kwargs

        match message_history:
            case "normal":
                solution_generator = SolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        api_keys=api_keys,
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "latest_only":
                solution_generator = LatestStateSolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        api_keys=api_keys,
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "reverse":
                solution_generator = ReverseOrderSolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        api_keys=api_keys,
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case _:
                raise NotImplementedError(
                    f"error: {message_history} has not been implemented in the Fix Code Command"
                )

        try:
            solution_generator.update_state(
                source_code=source_file.latest_content,
                esbmc_output=source_file.latest_verifier_output,
            )
        except ESBMCTimedOutException:
            print("error: ESBMC has timed out...")
            sys.exit(1)

        print()

        for attempt in range(1, max_attempts + 1):
            # Get a response. Use while loop to account for if the message stack
            # gets full, then need to compress and retry.
            while True:
                # Generate AI solution
                self.anim.start("Generating Solution... Please Wait")
                llm_solution, finish_reason = solution_generator.generate_solution()
                self.anim.stop()
                if finish_reason == FinishReason.length:
                    solution_generator.compress_message_stack()
                else:
                    source_file.update_content(llm_solution)
                    break

            # Print verbose lvl 2
            printvv("\nESBMC-AI Notice: Source Code Generation:")
            print_horizontal_line(2)
            printvv(source_file.latest_content)
            print_horizontal_line(2)
            printvv("")

            # Pass to ESBMC, a workaround is used where the file is saved
            # to a temporary location since ESBMC needs it in file format.
            self.anim.start("Verifying with ESBMC... Please Wait")
            exit_code, esbmc_output = ESBMCUtil.esbmc_load_source_code(
                source_file=source_file,
                source_file_content_index=-1,
                esbmc_params=esbmc_params,
                auto_clean=temp_auto_clean,
                timeout=verifier_timeout,
            )
            self.anim.stop()

            source_file.assign_verifier_output(esbmc_output)
            del esbmc_output

            # Print verbose lvl 2
            printvv("\nESBMC-AI Notice: ESBMC Output:")
            print_horizontal_line(2)
            printvv(source_file.latest_verifier_output)
            print_horizontal_line(2)

            # Solution found
            if exit_code == 0:
                self.on_solution_signal.emit(source_file.latest_content)

                if raw_conversation:
                    print_raw_conversation()

                printv("ESBMC-AI Notice: Successfully verified code")

                returned_source: str
                if generate_patches:
                    returned_source = source_file.get_patch(0, -1)
                else:
                    returned_source = source_file.latest_content

                return FixCodeCommandResult(True, returned_source)

            try:
                # Update state
                solution_generator.update_state(
                    source_file.latest_content, source_file.latest_verifier_output
                )
            except ESBMCTimedOutException:
                if raw_conversation:
                    print_raw_conversation()
                print("ESBMC-AI Notice: error: ESBMC has timed out...")
                sys.exit(1)

            # Failure case
            if attempt != max_attempts:
                print(f"ESBMC-AI Notice: Failure {attempt}/{max_attempts}: Retrying...")
            else:
                print(f"ESBMC-AI Notice: Failure {attempt}/{max_attempts}")

        if raw_conversation:
            print_raw_conversation()

        return FixCodeCommandResult(False, None)
