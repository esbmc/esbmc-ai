# Author: Yiannis Charalambous

from enum import Enum
import os
from pathlib import Path
import sys
from typing import Any
from pydantic import Field, field_validator
from typing_extensions import override

from esbmc_ai.base_component import BaseComponentConfig
from esbmc_ai.component_manager import ComponentManager
from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.ai_models import AIModel
from esbmc_ai.chats.solution_generator import (
    SolutionGenerator,
    FixCodeScenario,
)
from esbmc_ai.chats.template_key_provider import ESBMCTemplateKeyProvider
from esbmc_ai.verifiers.base_source_verifier import VerifierTimedOutException
from esbmc_ai.command_result import CommandResult
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.log_utils import get_log_level, print_horizontal_line
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
import esbmc_ai.prompt_utils as prompt_utils
from esbmc_ai.verifiers.esbmc import ESBMC


class FixCodeCommandResult(CommandResult):
    """Returned by the FixCodeCommand"""

    def __init__(
        self,
        successful: bool,
        attempts: int,
        repaired_source: str | None = None,
    ) -> None:
        super().__init__()
        self._successful: bool = successful
        self.attempts: int = attempts
        self.repaired_source: str | None = repaired_source

    @property
    @override
    def successful(self) -> bool:
        return self._successful

    @override
    def __str__(self) -> str:
        if self._successful and self.repaired_source is not None:
            return self.repaired_source

        return "Failed all attempts..."


class FixCodeCommandConfig(BaseComponentConfig):
    class VerifierOutputType(str, Enum):
        full = "full"
        ce = "ce"
        vp = "vp"

    verifier_output_type: str = Field(
        default=VerifierOutputType.full,
        description="The type of output from ESBMC in the fix code command.",
    )

    temperature: float = Field(
        default=0,
        description="The temperature of the LLM for the fix code command.",
    )

    max_attempts: int = Field(
        default=5,
        description="Fix code command max attempts.",
    )

    prompt_templates: dict[str, FixCodeScenario] = Field(
        default={
            "base": FixCodeScenario(
                initial="The ESBMC output is:\n\n```\n{esbmc_output}\n```\n\nThe source code is:\n\n```c\n{source_code}\n```\n Using the ESBMC output, show the fixed text.",
                system=[
                    {
                        "role": "system",
                        "content": "From now on, act as an Automated Code Repair Tool that repairs AI C code. You will be shown AI C code, along with ESBMC output. Pay close attention to the ESBMC output, which contains a stack trace along with the type of error that occurred and its location that you need to fix. Provide the repaired C code as output, as would an Automated Code Repair Tool. Aside from the corrected source code, do not output any other text.",
                    }
                ],
            ),
            "division by zero": FixCodeScenario(
                initial="The ESBMC output is:\n\n```\n{esbmc_output}\n```\n\nThe source code is:\n\n```c\n{source_code}\n```\n Using the ESBMC output, show the fixed text.",
                system=[
                    {
                        "role": "system",
                        "content": "Here's a C program with a vulnerability:\n```c\n{source_code}\n```\nA Formal Verification tool identified a division by zero issue:\n{esbmc_output}\nTask: Modify the C code to safely handle scenarios where division by zero might occur. The solution should prevent undefined behavior or crashes due to division by zero. \nGuidelines: Focus on making essential changes only. Avoid adding or modifying comments, and ensure the changes are precise and minimal.\nGuidelines: Ensure the revised code avoids undefined behavior and handles division by zero cases effectively.\nGuidelines: Implement safeguards (like comparison) to prevent division by zero instead of using literal divisions like 1.0/0.0.Output: Provide the corrected, complete C code. The solution should compile and run error-free, addressing the division by zero vulnerability.\nStart the code snippet with ```c and end with ```. Reply OK if you understand.",
                    },
                    {"role": "ai", "content": "OK."},
                ],
            ),
        },
        description="Scenario prompt templates for different types of bugs for the fix code command.",
    )

    @field_validator("verifier_output_type", mode="after")
    @classmethod
    def validate_verifier_output_type(cls, v: str) -> str:
        if v not in ["full", "vp", "ce"]:
            raise ValueError("verifier_output_type must be 'full', 'vp', or 'ce'")
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
        self.original_source_file: SourceFile
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

    @override
    def execute(self, **kwargs: Any) -> FixCodeCommandResult:
        # Handle kwargs
        source_file: SourceFile = SourceFile.load(
            self.global_config.solution.filenames[0],
            Path(os.getcwd()),
        )
        self.original_source_file = SourceFile(
            source_file.file_path, source_file.base_path, source_file.content
        )
        self.anim = (
            LoadingWidget() if self.global_config.loading_hints else BaseLoadingWidget()
        )
        # End of handle kwargs

        solution: Solution = Solution([])
        solution.add_source_file(source_file)

        self._logger.info(f"FixCodeConfig: {self._config}")

        verifier: Any = ComponentManager().get_verifier("esbmc")
        assert isinstance(verifier, ESBMC)
        verifier_result: VerifierOutput = verifier.verify_source(solution=solution)
        source_file.verifier_output = verifier_result

        if verifier_result.successful:
            self.logger.info("File verified successfully")
            returned_source: str
            if self.global_config.generate_patches:
                returned_source = source_file.get_diff(source_file)
            else:
                returned_source = source_file.content
            return FixCodeCommandResult(True, 0, returned_source)

        # Create the AI model with the specified parameters
        ai_model = AIModel.get_model(
            model=self.global_config.ai_model.id,
            temperature=self._config.temperature,
            url=self.global_config.ai_model.base_url,
        )

        solution_generator: SolutionGenerator = SolutionGenerator(
            ai_model=ai_model,
            scenarios=self._config.prompt_templates,
            esbmc_output_type=self._config.verifier_output_type,
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

        for attempt in range(1, self._config.max_attempts + 1):
            result: FixCodeCommandResult | None = self._attempt_repair(
                attempt=attempt,
                solution_generator=solution_generator,
                verifier=verifier,
                solution=solution,
            )
            if result:
                if self.global_config.generate_patches:
                    result.repaired_source = source_file.get_diff(
                        self.original_source_file
                    )

                return result

        return FixCodeCommandResult(False, self._config.max_attempts, None)

    def _attempt_repair(
        self,
        attempt: int,
        solution_generator: SolutionGenerator,
        solution: Solution,
        verifier: ESBMC,
    ) -> FixCodeCommandResult | None:
        source_file: SourceFile = solution.files[0]

        # Generate AI solution
        with self.anim("Generating Solution... Please Wait"):
            llm_solution = solution_generator.generate_solution()

            # Update the source file state
            source_file.content = llm_solution

        # Print verbose lvl 2
        print_horizontal_line(get_log_level(3))
        self._logger.debug("\nSource Code Generation:")
        self._logger.debug(source_file.content)
        print_horizontal_line(get_log_level(3))

        solution = solution.save_temp()

        # Pass to ESBMC, a workaround is used where the file is saved
        # to a temporary location since ESBMC needs it in file format.
        with self.anim("Verifying with ESBMC... Please Wait"):
            verifier_result: VerifierOutput = verifier.verify_source(solution=solution)

        source_file.verifier_output = verifier_result

        # Solution found
        if verifier_result.return_code == 0:

            self.logger.info("Successfully verified code")

            # Check if an output directory is specified and save to it
            if self.global_config.solution.output_dir:
                output_path: Path = (
                    self.global_config.solution.output_dir / source_file.file_path.name
                )
                if self.global_config.generate_patches:
                    output_path = output_path.parent / (output_path.name + ".patch")
                    source_file.save_diff(output_path, self.original_source_file)
                else:
                    source_file.save_file(output_path)
            return FixCodeCommandResult(True, attempt, source_file.content)

        try:
            # Update state
            solution_generator.update_state(
                source_file,
                source_file.verifier_output,
            )
        except VerifierTimedOutException:
            self.logger.error("ESBMC has timed out...")
            sys.exit(1)

        # Failure case
        if attempt != self._config.max_attempts:
            self.logger.info(
                f"Failure {attempt}/{self._config.max_attempts}: Retrying..."
            )
        else:
            self.logger.info(
                f"Failure {attempt}/{self._config.max_attempts}: Exiting..."
            )
