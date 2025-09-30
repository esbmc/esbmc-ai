# Author: Yiannis Charalambous

import os
from pathlib import Path
import sys
from typing import Any, Optional
from langchain.schema import HumanMessage
from pydantic import BaseModel, Field, field_validator
from typing_extensions import override
from esbmc_ai.base_component import BaseComponentConfig
from esbmc_ai.component_manager import ComponentManager
from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.ai_models import AIModel
from esbmc_ai.chats.solution_generator import (
    SolutionGenerator,
    LatestStateSolutionGenerator,
    ReverseOrderSolutionGenerator,
    FixCodeScenario,
    default_scenario,
)
from esbmc_ai.verifiers.base_source_verifier import VerifierTimedOutException
from esbmc_ai.command_result import CommandResult
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.log_utils import get_log_level, print_horizontal_line
from esbmc_ai.chat_response import list_to_base_messages
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
import esbmc_ai.prompt_utils as prompt_utils
from esbmc_ai.verifiers.esbmc import ESBMC


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


class FixCodeCommandConfig(BaseComponentConfig):
    verifier_output_type: str = Field(
        default="full",
        description="The type of output from ESBMC in the fix code command.",
    )

    temperature: float = Field(
        default=1.0,
        description="The temperature of the LLM for the fix code command.",
    )

    max_attempts: int = Field(
        default=5,
        description="Fix code command max attempts.",
    )

    message_history: str = Field(
        default="normal",
        description="The type of history to be shown in the fix code command.",
    )

    raw_conversation: bool = Field(
        default=False,
        description="Print the raw conversation at different parts of execution.",
    )

    source_code_format: str = Field(
        default="full",
        description="The source code format in the fix code prompt.",
    )

    prompt_templates: dict = Field(
        default={
            "base": {
                "initial": "The ESBMC output is:\n\n```\n$esbmc_output\n```\n\nThe source code is:\n\n```c\n$source_code\n```\n Using the ESBMC output, show the fixed text.",
                "system": [
                    {
                        "role": "System",
                        "content": "From now on, act as an Automated Code Repair Tool that repairs AI C code. You will be shown AI C code, along with ESBMC output. Pay close attention to the ESBMC output, which contains a stack trace along with the type of error that occurred and its location that you need to fix. Provide the repaired C code as output, as would an Automated Code Repair Tool. Aside from the corrected source code, do not output any other text.",
                    }
                ],
            },
            "division by zero": {
                "initial": "The ESBMC output is:\n\n```\n$esbmc_output\n```\n\nThe source code is:\n\n```c\n$source_code\n```\n Using the ESBMC output, show the fixed text.",
                "system": [
                    {
                        "role": "System",
                        "content": "Here's a C program with a vulnerability:\n```c\n$source_code\n```\nA Formal Verification tool identified a division by zero issue:\n$esbmc_output\nTask: Modify the C code to safely handle scenarios where division by zero might occur. The solution should prevent undefined behavior or crashes due to division by zero. \nGuidelines: Focus on making essential changes only. Avoid adding or modifying comments, and ensure the changes are precise and minimal.\nGuidelines: Ensure the revised code avoids undefined behavior and handles division by zero cases effectively.\nGuidelines: Implement safeguards (like comparison) to prevent division by zero instead of using literal divisions like 1.0/0.0.Output: Provide the corrected, complete C code. The solution should compile and run error-free, addressing the division by zero vulnerability.\nStart the code snippet with ```c and end with ```. Reply OK if you understand.",
                    },
                    {"role": "AI", "content": "OK."},
                ],
            },
        },
        description="Scenario prompt templates for different types of bugs for the fix code command.",
    )

    @field_validator("verifier_output_type", mode="after")
    @classmethod
    def validate_verifier_output_type(cls, v: str) -> str:
        if v not in ["full", "vp", "ce"]:
            raise ValueError("verifier_output_type must be 'full', 'vp', or 'ce'")
        return v

    @field_validator("message_history", mode="after")
    @classmethod
    def validate_message_history(cls, v: str) -> str:
        if v not in ["normal", "latest_only", "reverse"]:
            raise ValueError(
                'message_history can only be "normal", "latest_only", "reverse"'
            )
        return v

    @field_validator("source_code_format", mode="after")
    @classmethod
    def validate_source_code_format(cls, v: str) -> str:
        if not isinstance(v, str) or v not in ["full", "single"]:
            raise ValueError("source_code_format can only be 'full' or 'single'")
        return v


class FixCodeCommand(ChatCommand):
    """Command for automatically fixing code using a verifier."""

    def __init__(self) -> None:
        super().__init__(
            command_name="fix-code",
            help_message="Generates a solution for this code, and reevaluates it with ESBMC.",
        )
        # Set default config instance
        self._config: FixCodeCommandConfig = FixCodeCommandConfig()

        self.anim: BaseLoadingWidget

    @classmethod
    def _get_config_class(cls) -> type[BaseComponentConfig]:
        """Return the config class for this component."""
        return FixCodeCommandConfig

    @property
    @override
    def config(self) -> BaseComponentConfig:
        return self._config

    @config.setter
    def config(self, value: BaseComponentConfig) -> None:
        assert isinstance(value, FixCodeCommandConfig)
        self._config = value

    def print_raw_conversation(self, solution_generator: SolutionGenerator) -> None:
        """Debug prints the raw conversation"""
        print_horizontal_line(get_log_level())
        self.logger.info("ESBMC-AI Notice: Printing raw conversation...")
        all_messages = solution_generator._system_messages + solution_generator.messages
        messages: list[str] = [f"{msg.type}: {msg.content}" for msg in all_messages]
        self.logger.info("\n" + "\n\n".join(messages))
        self.logger.info("ESBMC-AI Notice: End of raw conversation")
        print_horizontal_line(get_log_level())

    def get_processed_prompt_templates(self) -> dict[str, FixCodeScenario]:
        """Process the prompt templates from config into FixCodeScenario objects."""
        raw_templates = self._config.prompt_templates

        # Validate that default scenario exists
        if default_scenario not in raw_templates:
            raise ValueError(
                f"Default scenario '{default_scenario}' not found in prompt_templates"
            )

        # Validate all templates
        for template in raw_templates.values():
            if not prompt_utils.validate_prompt_template(template):
                raise ValueError("Invalid prompt template found")

        # Convert to FixCodeScenario objects
        return {
            scenario: FixCodeScenario(
                initial=HumanMessage(content=conv["initial"]),
                system=list_to_base_messages(conv["system"]),
            )
            for scenario, conv in raw_templates.items()
        }

    @override
    def execute(self, **kwargs: Any) -> FixCodeCommandResult:
        # Handle kwargs
        source_file: SourceFile = SourceFile.load(
            self.global_config.solution.filenames[0],
            Path(os.getcwd()),
        )
        original_source_file: SourceFile = SourceFile(
            source_file.file_path, source_file.base_path, source_file.content
        )
        self.anim = (
            LoadingWidget() if self.global_config.loading_hints else BaseLoadingWidget()
        )
        generate_patches: bool = self.global_config.generate_patches
        message_history: str = self._config.message_history
        temperature: float = self._config.temperature
        source_code_format: str = self._config.source_code_format
        esbmc_output_format: str = self._config.verifier_output_type
        scenarios: dict[str, FixCodeScenario] = self.get_processed_prompt_templates()
        max_attempts: int = self._config.max_attempts
        raw_conversation: bool = self._config.raw_conversation
        entry_function: str = self.global_config.solution.entry_function
        output_dir: Path | None = self.global_config.solution.output_dir
        # End of handle kwargs

        solution: Solution = Solution([])
        solution.add_source_file(source_file)

        self._logger.info(f"Temperature: {temperature}")
        self._logger.info(f"Verifying function: {entry_function}")

        verifier: Any = ComponentManager().get_verifier("esbmc")
        assert isinstance(verifier, ESBMC)
        self._logger.info(f"Running verifier: {verifier.verifier_name}")
        verifier_result: VerifierOutput = verifier.verify_source(
            solution=solution, **kwargs
        )
        source_file.verifier_output = verifier_result

        if verifier_result.successful():
            self.logger.info("File verified successfully")
            returned_source: str
            if generate_patches:
                returned_source = source_file.get_diff(source_file)
            else:
                returned_source = source_file.content
            return FixCodeCommandResult(True, 0, returned_source)

        # Create the AI model with the specified parameters
        ai_model = AIModel.get_model(
            model=self.global_config.ai_model.id,
            temperature=temperature,
            url=self.global_config.ai_model.base_url,
        )

        match message_history:
            case "normal":
                solution_generator = SolutionGenerator(
                    ai_model=ai_model,
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "latest_only":
                solution_generator = LatestStateSolutionGenerator(
                    ai_model=ai_model,
                    scenarios=scenarios,
                    source_code_format=source_code_format,
                    esbmc_output_type=esbmc_output_format,
                )
            case "reverse":
                solution_generator = ReverseOrderSolutionGenerator(
                    ai_model=ai_model,
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
                source_file=source_file,
                verifier_output=source_file.verifier_output,
            )
        except VerifierTimedOutException:
            self.logger.error("ESBMC has timed out...")
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
                    result.repaired_source = source_file.get_diff(original_source_file)

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
        verifier: ESBMC,
        output_dir: Optional[Path],
        raw_conversation: bool,
    ) -> Optional[FixCodeCommandResult]:
        source_file: SourceFile = solution.files[0]

        # Get a response. Use while loop to account for if the message stack
        # gets full, then need to compress and retry.
        while True:
            # Generate AI solution
            with self.anim("Generating Solution... Please Wait"):
                llm_solution = solution_generator.generate_solution()

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
            verifier_result: VerifierOutput = verifier.verify_source(solution=solution)

        source_file.verifier_output = verifier_result

        # Print verbose lvl 2
        self._logger.debug("\nESBMC-AI Notice: ESBMC Output:")
        print_horizontal_line(get_log_level(3))
        self._logger.debug(source_file.verifier_output.output)
        print_horizontal_line(get_log_level(3))

        # Solution found
        if verifier_result.return_code == 0:
            if raw_conversation:
                self.print_raw_conversation(solution_generator)

            self.logger.info("Successfully verified code")

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
                source_file,
                source_file.verifier_output,
            )
        except VerifierTimedOutException:
            if raw_conversation:
                self.print_raw_conversation(solution_generator)
            self.logger.error("ESBMC has timed out...")
            sys.exit(1)

        # Failure case
        if attempt != max_attempts:
            self.logger.info(f"Failure {attempt}/{max_attempts}: Retrying...")
        else:
            self.logger.info(f"Failure {attempt}/{max_attempts}: Exiting...")
