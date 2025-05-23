# Author: Yiannis Charalambous

from pathlib import Path
import sys
from typing import Any, Optional
from typing_extensions import override

from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import FinishReason
from esbmc_ai.chats import LatestStateSolutionGenerator, SolutionGenerator
from esbmc_ai.verifiers.base_source_verifier import (
    VerifierTimedOutException,
    BaseSourceVerifier,
)
from esbmc_ai.command_result import CommandResult
from esbmc_ai.config import Config, FixCodeScenario
from esbmc_ai.chats.reverse_order_solution_generator import (
    ReverseOrderSolutionGenerator,
)
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.log_utils import get_log_level, print_horizontal_line

from ..msg_bus import Signal
from ..loading_widget import BaseLoadingWidget, LoadingWidget


class FixCodeCommandResult(CommandResult):
    """Returned by the FixCodeCommand"""

    def __init__(
        self,
        successful: bool,
        attempts: int,
        repaired_source: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._successful: bool = successful
        self.attempts: int = attempts
        self.repaired_source: Optional[str] = repaired_source

    @property
    @override
    def successful(self) -> bool:
        return self._successful

    @override
    def __str__(self) -> str:
        if self._successful and self.repaired_source is not None:
            return self.repaired_source

        return "ESBMC-AI Notice: Failed all attempts..."


class FixCodeCommand(ChatCommand):
    """Command for automatically fixing code using a verifier."""

    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        self.anim: BaseLoadingWidget

    def print_raw_conversation(self, solution_generator: SolutionGenerator) -> None:
        """Debug prints the raw conversation"""
        print_horizontal_line(0)
        print("ESBMC-AI Notice: Printing raw conversation...")
        all_messages = solution_generator._system_messages + solution_generator.messages
        messages: list[str] = [f"{msg.type}: {msg.content}" for msg in all_messages]
        print("\n" + "\n\n".join(messages))
        print("ESBMC-AI Notice: End of raw conversation")

    @override
    def execute(self, **kwargs: Any) -> FixCodeCommandResult:

        self._config = Config()

        # Handle kwargs
        source_file: SourceFile = kwargs["source_file"]
        original_source_file: SourceFile = SourceFile(
            source_file.file_path, source_file.base_path, source_file.content
        )
        self.anim = (
            LoadingWidget()
            if self.get_config_value("loading_hints")
            else BaseLoadingWidget()
        )
        generate_patches: bool = self.get_config_value("generate_patches")
        message_history: str = self.get_config_value("fix_code.message_history")
        ai_model: AIModel = self.get_config_value("ai_model")
        temperature: float = self.get_config_value("fix_code.temperature")
        max_tries: int = self.get_config_value("fix_code.max_attempts")
        timeout: int = self.get_config_value("llm_requests.timeout")
        source_code_format: str = self.get_config_value("source_code_format")
        esbmc_output_format: str = self.get_config_value("verifier.esbmc.output_type")
        scenarios: dict[str, FixCodeScenario] = self.get_config_value(
            "prompt_templates.fix_code"
        )
        max_attempts: int = self.get_config_value("fix_code.max_attempts")
        raw_conversation: bool = self.get_config_value("fix_code.raw_conversation")
        entry_function: str = self.get_config_value("solution.entry_function")
        output_dir: Path = self.get_config_value("solution.output_dir")
        # End of handle kwargs

        solution: Solution = Solution([])
        solution.add_source_file(source_file)

        self._logger.info(f"Temperature: {temperature}")
        self._logger.info(f"Verifying function: {entry_function}")

        verifier: BaseSourceVerifier = VerifierRunner().verifier
        self._logger.info(f"Running verifier: {verifier.verifier_name}")
        verifier_result: VerifierOutput = verifier.verify_source(solution, **kwargs)
        source_file.verifier_output = verifier_result

        if verifier_result.successful():
            print("File verified successfully")
            returned_source: str
            if generate_patches:
                returned_source = source_file.get_patch(source_file)
            else:
                returned_source = source_file.content
            return FixCodeCommandResult(True, 0, returned_source)

        match message_history:
            case "normal":
                solution_generator = SolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    verifier=verifier,
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "latest_only":
                solution_generator = LatestStateSolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    verifier=verifier,
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "reverse":
                solution_generator = ReverseOrderSolutionGenerator(
                    ai_model=ai_model,
                    llm=ai_model.create_llm(
                        temperature=temperature,
                        requests_max_tries=max_tries,
                        requests_timeout=timeout,
                    ),
                    verifier=verifier,
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
                source_code=source_file.content,
                esbmc_output=source_file.verifier_output.output,
            )
        except VerifierTimedOutException:
            print("ESBMC-AI Notice: ESBMC has timed out...")
            sys.exit(1)

        print()

        for attempt in range(1, max_attempts + 1):
            result: Optional[FixCodeCommandResult] = self._attempt_repair(
                attempt=attempt,
                solution_generator=solution_generator,
                verifier=verifier,
                max_attempts=max_attempts,
                output_dir=output_dir,
                solution=solution,
                raw_conversation=raw_conversation,
            )
            if result:
                if raw_conversation:
                    self.print_raw_conversation(solution_generator)

                if generate_patches:
                    result.repaired_source = source_file.get_patch(original_source_file)

                return result

        if raw_conversation:
            self.print_raw_conversation(solution_generator)

        return FixCodeCommandResult(False, max_attempts, None)

    def _attempt_repair(
        self,
        attempt: int,
        max_attempts: int,
        solution_generator: SolutionGenerator,
        solution: Solution,
        verifier: BaseSourceVerifier,
        output_dir: Optional[Path],
        raw_conversation: bool,
    ) -> Optional[FixCodeCommandResult]:
        source_file: SourceFile = solution.files[0]

        # Get a response. Use while loop to account for if the message stack
        # gets full, then need to compress and retry.
        while True:
            # Generate AI solution
            with self.anim("Generating Solution... Please Wait"):
                llm_solution, finish_reason = solution_generator.generate_solution()

            if finish_reason == FinishReason.length:
                solution_generator.compress_message_stack()
            else:
                # Update the source file state
                source_file.content = llm_solution
                break

        # Print verbose lvl 2
        self._logger.debug("\nESBMC-AI Notice: Source Code Generation:")
        print_horizontal_line(get_log_level(3))
        self._logger.debug(source_file.content)
        print_horizontal_line(get_log_level(3))
        self._logger.debug("")

        solution = solution.save_temp()

        # Pass to ESBMC, a workaround is used where the file is saved
        # to a temporary location since ESBMC needs it in file format.
        with self.anim("Verifying with ESBMC... Please Wait"):
            verifier_result: VerifierOutput = verifier.verify_source(solution)

        source_file.verifier_output = verifier_result

        # Print verbose lvl 2
        self._logger.debug("\nESBMC-AI Notice: ESBMC Output:")
        print_horizontal_line(get_log_level(3))
        self._logger.debug(source_file.verifier_output.output)
        print_horizontal_line(get_log_level(3))

        # Solution found
        if verifier_result.return_code == 0:
            self.on_solution_signal.emit(source_file.content)

            if raw_conversation:
                self.print_raw_conversation(solution_generator)

            print("ESBMC-AI Notice: Successfully verified code")

            # Check if an output directory is specified and save to it
            if output_dir:
                assert (
                    output_dir.is_dir()
                ), "FixCodeCommand: Output directory needs to be valid"
                source_file.save_file(output_dir / source_file.file_path.name)
            return FixCodeCommandResult(True, attempt, source_file.content)

        try:
            # Update state
            solution_generator.update_state(
                source_file.content, source_file.verifier_output.output
            )
        except VerifierTimedOutException:
            if raw_conversation:
                self.print_raw_conversation(solution_generator)
            print("ESBMC-AI Notice: error: ESBMC has timed out...")
            sys.exit(1)

        # Failure case
        if attempt != max_attempts:
            print(f"ESBMC-AI Notice: Failure {attempt}/{max_attempts}: Retrying...")
        else:
            print(f"ESBMC-AI Notice: Failure {attempt}/{max_attempts}: Exiting...")
