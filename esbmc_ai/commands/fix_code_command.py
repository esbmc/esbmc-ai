# Author: Yiannis Charalambous

import sys
from typing import Any, Tuple
from typing_extensions import override

from esbmc_ai.chat_response import FinishReason
from esbmc_ai.latest_state_solution_generator import LatestStateSolutionGenerator
from esbmc_ai.reverse_order_solution_generator import ReverseOrderSolutionGenerator

from .chat_command import ChatCommand
from .. import config
from ..msg_bus import Signal
from ..loading_widget import create_loading_widget
from ..esbmc_util import (
    esbmc_get_error_type,
    esbmc_load_source_code,
)
from ..solution_generator import (
    ESBMCTimedOutException,
    SolutionGenerator,
)
from ..logging import print_horizontal_line, printv, printvv


class FixCodeCommand(ChatCommand):
    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim = create_loading_widget()

    @override
    def execute(self, **kwargs: Any) -> Tuple[bool, str]:
        def print_raw_conversation() -> None:
            print_horizontal_line(0)
            print("ESBMC-AI Notice: Printing raw conversation...")
            all_messages = solution_generator._system_messages.copy()
            all_messages.extend(solution_generator.messages.copy())
            messages: list[str] = [f"{msg.type}: {msg.content}" for msg in all_messages]
            print("\n" + "\n\n".join(messages))
            print("ESBMC-AI Notice: End of raw conversation")

        file_name: str = kwargs["file_name"]
        source_code: str = kwargs["source_code"]
        esbmc_output: str = kwargs["esbmc_output"]

        # Parse the esbmc output here and determine what "Scenario" to use.
        scenario: str = esbmc_get_error_type(esbmc_output)

        printv(f"Scenario: {scenario}")
        printv(
            f"Using dynamic prompt..."
            if scenario in config.chat_prompt_generator_mode.scenarios
            else "Using generic prompt..."
        )

        match config.fix_code_message_history:
            case "normal":
                solution_generator = SolutionGenerator(
                    ai_model_agent=config.chat_prompt_generator_mode,
                    ai_model=config.ai_model,
                    llm=config.ai_model.create_llm(
                        api_keys=config.api_keys,
                        temperature=config.chat_prompt_generator_mode.temperature,
                        requests_max_tries=config.requests_max_tries,
                        requests_timeout=config.requests_timeout,
                    ),
                    scenario=scenario,
                    source_code_format=config.source_code_format,
                    esbmc_output_type=config.esbmc_output_type,
                )
            case "latest_only":
                solution_generator = LatestStateSolutionGenerator(
                    ai_model_agent=config.chat_prompt_generator_mode,
                    ai_model=config.ai_model,
                    llm=config.ai_model.create_llm(
                        api_keys=config.api_keys,
                        temperature=config.chat_prompt_generator_mode.temperature,
                        requests_max_tries=config.requests_max_tries,
                        requests_timeout=config.requests_timeout,
                    ),
                    scenario=scenario,
                    source_code_format=config.source_code_format,
                    esbmc_output_type=config.esbmc_output_type,
                )
            case "reverse":
                solution_generator = ReverseOrderSolutionGenerator(
                    ai_model_agent=config.chat_prompt_generator_mode,
                    ai_model=config.ai_model,
                    llm=config.ai_model.create_llm(
                        api_keys=config.api_keys,
                        temperature=config.chat_prompt_generator_mode.temperature,
                        requests_max_tries=config.requests_max_tries,
                        requests_timeout=config.requests_timeout,
                    ),
                    scenario=scenario,
                    source_code_format=config.source_code_format,
                    esbmc_output_type=config.esbmc_output_type,
                )
            case _:
                raise NotImplementedError(
                    f"error: {config.fix_code_message_history} has not been implemented in the Fix Code Command"
                )

        try:
            solution_generator.update_state(
                source_code=source_code,
                esbmc_output=esbmc_output,
            )
        except ESBMCTimedOutException:
            print("error: ESBMC has timed out...")
            sys.exit(1)

        print()

        max_retries: int = config.fix_code_max_attempts
        for idx in range(max_retries):
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
                    source_code = llm_solution
                    break

            # Print verbose lvl 2
            printvv("\nESBMC-AI Notice: Source Code Generation:")
            print_horizontal_line(2)
            printvv(source_code)
            print_horizontal_line(2)
            printvv("")

            # Pass to ESBMC, a workaround is used where the file is saved
            # to a temporary location since ESBMC needs it in file format.
            self.anim.start("Verifying with ESBMC... Please Wait")
            exit_code, esbmc_output = esbmc_load_source_code(
                file_path=file_name,
                source_code=source_code,
                esbmc_params=config.esbmc_params,
                auto_clean=config.temp_auto_clean,
                timeout=config.verifier_timeout,
            )
            self.anim.stop()

            # Print verbose lvl 2
            printvv("\nESBMC-AI Notice: ESBMC Output:")
            print_horizontal_line(2)
            printvv(esbmc_output)
            print_horizontal_line(2)

            # Solution found
            if exit_code == 0:
                self.on_solution_signal.emit(source_code)

                if config.raw_conversation:
                    print_raw_conversation()

                printv("ESBMC-AI Notice: Successfully verified code")

                return False, source_code

            try:
                # Update state
                solution_generator.update_state(source_code, esbmc_output)
            except ESBMCTimedOutException:
                if config.raw_conversation:
                    print_raw_conversation()
                print("ESBMC-AI Notice: error: ESBMC has timed out...")
                sys.exit(1)

            # Failure case
            print(
                f"ESBMC-AI Notice: Failure {idx+1}/{max_retries}" + ": Retrying..."
                if idx != max_retries - 1
                else ""
            )

        if config.raw_conversation:
            print_raw_conversation()

        return True, "ESBMC-AI Notice: Failed all attempts..."
