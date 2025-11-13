# Author: Yiannis Charalambous

from enum import Enum
import os
from pathlib import Path
from typing import Any
from pydantic import Field, field_validator
from typing_extensions import override
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from esbmc_ai.base_component import BaseComponentConfig
from esbmc_ai.component_manager import ComponentManager
from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.ai_models import AIModel
from esbmc_ai.chats.solution_generator import SolutionGenerator
from esbmc_ai.command_result import CommandResult
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.verifiers.esbmc import ESBMC, ESBMCOutput


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

    initial: str = Field(
        default="ESBMC found an error in the code:\n\nError Type: {{oracle_output.error_type}}\nError Message: {{oracle_output.error_message}}\nError Location: {{oracle_output.error_file}}:{{oracle_output.error_line}}\n\nStack Trace:\n{{oracle_output.primary_issue.stack_trace_formatted}}\n\n{% if is_verifier_issue(oracle_output.primary_issue) and oracle_output.primary_issue.counterexample | length > 0 %}Counterexample:\n{{oracle_output.primary_issue.counterexample_formatted}}\n\n{% endif %}The source code is:\n\n```c\n{{solution.files[0].content}}\n```\n\nUsing the error information above, show the fixed text.",
        description="Initial prompt for the first repair attempt. Uses structured oracle output fields.",
    )

    retry_prompt: str = Field(
        default="The previous attempt failed. ESBMC found an error:\n\nError Type: {{oracle_output.error_type}}\nError Message: {{oracle_output.error_message}}\nError Location: {{oracle_output.error_file}}:{{oracle_output.error_line}}\n\nStack Trace:\n{{oracle_output.primary_issue.stack_trace_formatted}}\n\n{% if is_verifier_issue(oracle_output.primary_issue) and oracle_output.primary_issue.counterexample | length > 0 %}Counterexample:\n{{oracle_output.primary_issue.counterexample_formatted}}\n\n{% endif %}The source code is:\n\n```c\n{{solution.files[0].content}}\n```\n\nPlease review the conversation history to see what was tried before. Using the error information above and learning from previous failed attempts, show the fixed text.",
        description="Prompt used for retry attempts after the initial attempt fails. Uses structured oracle output fields and can reference conversation history.",
    )

    system: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "From now on, act as an Automated Code Repair Tool that repairs C code. You will be shown C code along with structured error information from ESBMC verification. Pay close attention to the error type, error message, and error location provided. Use this information to identify and fix the bug. Provide the repaired C code as output, as would an Automated Code Repair Tool. Aside from the corrected source code, do not output any other text.",
        }
    ]

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
    def execute(self) -> FixCodeCommandResult:
        self.logger.warn(
            "Fix Code Command is a demonstration of the ESBMC-AI "
            + "API capabilities. Do not use for advanced repair tasks.\n"
        )
        # Handle kwargs
        source_file: SourceFile = SourceFile.load(
            self.global_config.solution.filenames[0]
        )
        self.original_source_file = SourceFile(
            file_path=source_file.file_path, content=source_file.content
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
        verifier_output: VerifierOutput = verifier.verify_source(solution=solution)
        assert isinstance(verifier_output, ESBMCOutput)

        if verifier_output.successful:
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

        # Convert system messages from dict format to BaseMessage objects
        system_messages: list[BaseMessage] = []
        for msg in self._config.system:
            role = msg.get("role", "system")
            content = msg.get("content", "")
            if role == "system":
                system_messages.append(SystemMessage(content=content))
            elif role == "human":
                system_messages.append(HumanMessage(content=content))
            elif role == "assistant" or role == "ai":
                system_messages.append(AIMessage(content=content))

        # Create the initial and retry message templates
        initial_prompt = PromptTemplate.from_template(self._config.initial)
        retry_prompt = PromptTemplate.from_template(self._config.retry_prompt)

        solution_generator: SolutionGenerator = SolutionGenerator(
            ai_model=ai_model,
            system_message=system_messages,
            esbmc_output_type=self._config.verifier_output_type,
        )

        print()

        for attempt in range(1, self._config.max_attempts + 1):
            # Use initial prompt for first attempt, retry prompt for subsequent attempts
            prompt = initial_prompt if attempt == 1 else retry_prompt

            result: FixCodeCommandResult | None
            result, verifier_output = self._attempt_repair(
                attempt=attempt,
                solution_generator=solution_generator,
                prompt=prompt,
                verifier=verifier,
                solution=solution,
                verifier_output=verifier_output,
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
        prompt: PromptTemplate,
        solution: Solution,
        verifier: ESBMC,
        verifier_output: ESBMCOutput,
    ) -> tuple[FixCodeCommandResult | None, ESBMCOutput]:
        source_file: SourceFile = solution.files[0]

        # Generate AI solution
        with self.anim("Generating Solution... Please Wait"):
            llm_solution = solution_generator.generate_solution(
                initial_message_prompt=prompt,
                solution=solution,
                verifier_output=verifier_output,
            )

            # Update the source file state
            source_file.content = llm_solution

        solution = solution.save_temp()

        # Pass to ESBMC, a workaround is used where the file is saved
        # to a temporary location since ESBMC needs it in file format.
        with self.anim("Verifying with ESBMC... Please Wait"):
            verifier_output = verifier.verify_source(solution=solution)
            assert isinstance(verifier_output, ESBMCOutput)

        # Solution found
        if verifier_output.return_code == 0:

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
            return FixCodeCommandResult(True, attempt, source_file.content), verifier_output

        # Failure case
        if attempt != self._config.max_attempts:
            self.logger.info(
                f"Failure {attempt}/{self._config.max_attempts}: Retrying..."
            )
        else:
            self.logger.info(
                f"Failure {attempt}/{self._config.max_attempts}: Exiting..."
            )

        return None, verifier_output
