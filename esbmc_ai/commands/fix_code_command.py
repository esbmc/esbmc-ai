# Author: Yiannis Charalambous

from pathlib import Path
import sys
from typing import Any, Optional
from typing_extensions import override

from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.ai_models import AIModel
from esbmc_ai.api_key_collection import APIKeyCollection
from esbmc_ai.chat_response import FinishReason
from esbmc_ai.chats import LatestStateSolutionGenerator, SolutionGenerator
from esbmc_ai.verifiers.base_source_verifier import (
    VerifierTimedOutException,
    BaseSourceVerifier,
)
from esbmc_ai.commands.command_result import CommandResult
from esbmc_ai.config import FixCodeScenario
from esbmc_ai.chats.reverse_order_solution_generator import (
    ReverseOrderSolutionGenerator,
)
from esbmc_ai.verifier_runner import VerifierRunner
from esbmc_ai.verifier_output import VerifierOutput

from .chat_command import ChatCommand
from ..msg_bus import Signal
from ..loading_widget import BaseLoadingWidget
from ..logging import print_horizontal_line, printv, printvvv


class FixCodeCommandResult(CommandResult):
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
        return (
            self.repaired_source
            if self._successful and self.repaired_source != None
            else "ESBMC-AI Notice: Failed all attempts..."
        )


class FixCodeCommand(ChatCommand):
    """Command for automatically fixing code using a verifier."""

    on_solution_signal: Signal = Signal()

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )

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

        # Handle kwargs
        source_file: SourceFile = kwargs["source_file"]
        original_source_file: SourceFile = SourceFile(
            source_file.file_path, source_file.content
        )

        generate_patches: bool = (
            kwargs["generate_patches"] if "generate_patches" in kwargs else False
        )

        message_history: str = (
            kwargs["message_history"] if "message_history" in kwargs else "normal"
        )

        api_keys: APIKeyCollection = kwargs["api_keys"]
        ai_model: AIModel = kwargs["ai_model"]
        temperature: float = kwargs["temperature"]
        max_tries: int = kwargs["requests_max_tries"]
        timeout: int = kwargs["requests_timeout"]
        source_code_format: str = kwargs["source_code_format"]
        esbmc_output_format: str = kwargs["esbmc_output_format"]
        scenarios: dict[str, FixCodeScenario] = kwargs["scenarios"]
        max_attempts: int = kwargs["max_attempts"]
        raw_conversation: bool = (
            kwargs["raw_conversation"] if "raw_conversation" in kwargs else False
        )
        output_dir: Optional[Path] = (
            kwargs["output_dir"] if "output_dir" in kwargs else None
        )
        self.anim: BaseLoadingWidget = (
            kwargs["anim"] if "anim" in kwargs else BaseLoadingWidget()
        )
        entry_function: str = (
            kwargs["entry_function"] if "entry_function" in kwargs else "main"
        )
        # End of handle kwargs

        solution: Solution = Solution()
        solution.add_source_file(source_file)

        printv(f"Temperature: {temperature}")
        printv(f"Verifying function: {entry_function}")

        verifier: BaseSourceVerifier = VerifierRunner().verifier
        printv(f"Running verifier: {verifier.verifier_name}")
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
                        api_keys=api_keys,
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
                        api_keys=api_keys,
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
                        api_keys=api_keys,
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
                **kwargs,
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
        source_file: SourceFile,
        verifier: BaseSourceVerifier,
        output_dir: Optional[Path],
        raw_conversation: bool,
        **kwargs: Any,
    ) -> Optional[FixCodeCommandResult]:
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
        printvvv("\nESBMC-AI Notice: Source Code Generation:")
        print_horizontal_line(3)
        printvvv(source_file.content)
        print_horizontal_line(3)
        printvvv("")

        solution: Solution = Solution()
        solution.add_source_file(source_file)

        # Pass to ESBMC, a workaround is used where the file is saved
        # to a temporary location since ESBMC needs it in file format.
        with self.anim("Verifying with ESBMC... Please Wait"):
            verifier_result: VerifierOutput = verifier.verify_source(solution, **kwargs)

        source_file.verifier_output = verifier_result

        # Print verbose lvl 2
        printvvv("\nESBMC-AI Notice: ESBMC Output:")
        print_horizontal_line(3)
        printvvv(source_file.verifier_output.output)
        print_horizontal_line(3)

        # Solution found
        if verifier_result.return_code == 0:
            self.on_solution_signal.emit(source_file.content)

            if raw_conversation:
                self.print_raw_conversation(solution_generator)

            printv("ESBMC-AI Notice: Successfully verified code")

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
