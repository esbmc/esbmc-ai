# Author: Yiannis Charalambous

from os import get_terminal_size
from time import sleep
from typing import Any, Tuple
from typing_extensions import override
from langchain.schema import AIMessage, HumanMessage

from esbmc_ai.chat_response import FinishReason

from .chat_command import ChatCommand
from .. import config
from ..msg_bus import Signal
from ..loading_widget import create_loading_widget
from ..esbmc_util import esbmc_load_source_code
from ..solution_generator import SolutionGenerator
from ..logging import printv, printvv

# TODO Remove built in messages and move them to config.


class FixCodeCommand(ChatCommand):
    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim = create_loading_widget()

    def _resolve_scenario(self, esbmc_output: str) -> str:
        # Start search from the marker.
        marker: str = "Violated property:\n"
        violated_property_index: int = esbmc_output.rfind(marker) + len(marker)
        from_loc_error_msg: str = esbmc_output[violated_property_index:]
        # Find second new line which contains the location of the violated
        # property and that should point to the line with the type of error.
        # In this case, the type of error is the "scenario".
        scenario_index: int = from_loc_error_msg.find("\n")
        scenario: str = from_loc_error_msg[scenario_index + 1 :]
        scenario_end_l_index: int = scenario.find("\n")
        scenario = scenario[:scenario_end_l_index].strip()
        return scenario

    @override
    def execute(self, **kwargs: Any) -> Tuple[bool, str]:
        file_name: str = kwargs["file_name"]
        source_code: str = kwargs["source_code"]
        esbmc_output: str = kwargs["esbmc_output"]

        wait_time: int = int(config.consecutive_prompt_delay)
        # Create time left animation to show how much time left between API calls
        # This is done by creating a list of all the numbers to be displayed and
        # setting the animation delay to 1 second.
        wait_anim = create_loading_widget(
            anim_speed=1,
            animation=[str(num) for num in range(wait_time, 0, -1)],
        )

        # Parse the esbmc output here and determine what "Scenario" to use.
        scenario: str = self._resolve_scenario(esbmc_output)

        printv(f"Scenario: {scenario}")
        printv(
            f"Using dynamic prompt..."
            if scenario in config.chat_prompt_generator_mode.scenarios
            else "Using generic prompt..."
        )

        llm = config.ai_model.create_llm(
            api_keys=config.api_keys,
            temperature=config.chat_prompt_generator_mode.temperature,
        )

        solution_generator = SolutionGenerator(
            ai_model_agent=config.chat_prompt_generator_mode,
            source_code=source_code,
            esbmc_output=esbmc_output,
            ai_model=config.ai_model,
            llm=llm,
            scenario=scenario,
        )

        print()

        max_retries: int = 10
        for idx in range(max_retries):
            # Get a response. Use while loop to account for if the message stack
            # gets full, then need to compress and retry.
            response: str = ""
            while True:
                # Generate AI solution
                self.anim.start("Generating Solution... Please Wait")
                response, finish_reason = solution_generator.generate_solution()
                self.anim.stop()
                if finish_reason == FinishReason.length:
                    self.anim.start("Compressing message stack... Please Wait")
                    solution_generator.compress_message_stack()
                    self.anim.stop()
                else:
                    break

            # Print verbose lvl 2
            printvv("\nGeneration:")
            printvv("-" * get_terminal_size().columns)
            printvv(response)
            printvv("-" * get_terminal_size().columns)
            printvv("")

            # Pass to ESBMC, a workaround is used where the file is saved
            # to a temporary location since ESBMC needs it in file format.
            self.anim.start("Verifying with ESBMC... Please Wait")
            exit_code, esbmc_output, esbmc_err_output = esbmc_load_source_code(
                file_path=file_name,
                source_code=str(response),
                esbmc_params=config.esbmc_params,
                auto_clean=config.temp_auto_clean,
            )
            self.anim.stop()

            # Print verbose lvl 2
            printvv("-" * get_terminal_size().columns)
            printvv(esbmc_output)
            printvv(esbmc_err_output)
            printvv("-" * get_terminal_size().columns)

            if exit_code == 0:
                self.on_solution_signal.emit(response)
                return False, response

            # Failure case
            print(f"Failure {idx+1}/{max_retries}: Retrying...")
            # If final iteration no need to sleep.
            if idx < max_retries - 1:
                wait_anim.start(f"Sleeping due to rate limit:")
                sleep(config.consecutive_prompt_delay)
                wait_anim.stop()

                # Inform solution generator chat about the ESBMC response.
                if exit_code != 1:
                    # The program did not compile.
                    solution_generator.push_to_message_stack(
                        message=HumanMessage(
                            content=f"The source code you provided does not compile. Fix the compilation errors. Use ESBMC output to fix the compilation errors:\n\n```\n{esbmc_output}\n```"
                        )
                    )
                else:
                    solution_generator.push_to_message_stack(
                        message=HumanMessage(
                            content=f"ESBMC has reported that verification failed, use the ESBMC output to find out what is wrong, and fix it. Here is ESBMC output:\n\n```\n{esbmc_output}\n```"
                        )
                    )

                solution_generator.push_to_message_stack(
                    AIMessage(content="Understood.")
                )

        return True, "Failed all attempts..."
