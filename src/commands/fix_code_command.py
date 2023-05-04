# Author: Yiannis Charalambous

from time import sleep

import src.config as config

from src.commands.chat_command import ChatCommand
from src.loading_widget import LoadingWidget
from src.esbmc import esbmc_load_source_code
from src.solution_generator import SolutionGenerator


class FixCodeCommand(ChatCommand):
    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim = LoadingWidget()

    def execute(self, source_code: str, esbmc_output: str):
        anim = self.anim
        solution_generator = SolutionGenerator(
            system_messages=config.chat_prompt_generator_mode.system_messages,
            initial_prompt=config.chat_prompt_generator_mode.initial_prompt,
            source_code=source_code,
            esbmc_output=esbmc_output,
            model=config.ai_model,
            # TODO Make this loadable from config file.
            temperature=1.1,
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
                print("\n\nassistant: Here is the corrected code, verified with ESBMC:")
                print(f"```\n{response}\n```")

                return False, response
            elif exit_code != 1:
                print("Error: AI model has probably output text in the source code...")
                print(f"ESBMC Error: {esbmc_output}")
                return True, esbmc_output

            # Failure case
            print(f"Failure {idx+1}/{max_retries}: Retrying...")
            # Final iteration no need to sleep.
            if idx < max_retries - 1:
                anim.start(
                    f"Sleeping {config.consecutive_prompt_delay} seconds due to rate limit..."
                )
                sleep(config.consecutive_prompt_delay)
                anim.stop()

        return True, "Failed all attempts..."
