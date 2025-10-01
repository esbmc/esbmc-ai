# Author: Yiannis Charalambous 2023

"""Contains code for automatically repairing code using ESBMC."""

from dataclasses import replace
from typing import Annotated
from langchain_core.prompts.chat import MessageLikeRepresentation
from pydantic import BaseModel, Field, SkipValidation
from langchain.schema import BaseMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from pydantic_settings import NoDecode

from esbmc_ai.solution import SourceFile
from esbmc_ai.verifiers.base_source_verifier import (
    SourceCodeParseError,
    VerifierTimedOutException,
)
from esbmc_ai.chats.template_key_provider import (
    ESBMCTemplateKeyProvider,
    TemplateKeyProvider,
)
from esbmc_ai.verifiers.esbmc import ESBMCOutput
from esbmc_ai.chats.template_renderer import KeyTemplateRenderer

default_scenario: str = "base"


class FixCodeScenario(BaseModel):
    initial: str = Field(default="")
    # Going to be manually instantiated by FixCodeCommandConfig
    system: list[SkipValidation[MessageLikeRepresentation]] = Field(
        default_factory=list,
    )


def apply_formatting(esbmc_output: ESBMCOutput, format: str) -> str:
    """Gets the formatted output ESBMC output, based on the esbmc_output_type
    passed."""
    # Check for parsing error
    if "ERROR: PARSING ERROR" in esbmc_output.output:
        # Parsing errors are usually small in nature.
        raise SourceCodeParseError()

    if "ERROR: Timed out" in esbmc_output.output:
        raise VerifierTimedOutException()

    match format:
        case "vp":
            value: str | None = esbmc_output.get_violated_property()
            if not value:
                raise ValueError("Not found violated property." + esbmc_output.output)
            return value
        case "ce":
            value: str | None = esbmc_output._esbmc_get_counter_example()
            if not value:
                raise ValueError("Not found counterexample.")
            return value
        case "full":
            return esbmc_output.output
        case _:
            raise ValueError(f"Not a valid ESBMC output type: {format}")


class SolutionGenerator:
    """SolutionGenerator is a simple conversation-based automated program repair
    class. The class works in a cycle, by first calling update_state with the
    new source_code and esbmc_output, then by calling generate_solution. The
    class supports scenarios to customize the system message and initial prompt
    based on the"""

    def __init__(
        self,
        scenarios: dict[str, FixCodeScenario],
        ai_model: BaseChatModel,
        esbmc_output_type: str = "full",
    ) -> None:
        """Initializes the solution generator."""
        super().__init__()

        self.ai_model: BaseChatModel = ai_model
        self.template_key_provider: TemplateKeyProvider = ESBMCTemplateKeyProvider()
        self.messages: list[BaseMessage] = []

        self.scenarios: dict[str, FixCodeScenario] = scenarios
        self.scenario: str = ""

        self.esbmc_output_type: str = esbmc_output_type

        self.source_code: SourceFile | None = None
        self.esbmc_output: ESBMCOutput | None = None
        self.invokations: int = 0

    @staticmethod
    def extract_code_from_solution(solution: str) -> str:
        """Strip the source code of any leftover text as sometimes the AI model
        will generate text and formatting despite being told not to."""
        try:
            code_start: int = solution.index("```") + 3
            assert code_start != -1

            # Remove up until the new line, because usually there's a language
            # specification after the 3 ticks ```c...
            code_start = solution.index("\n", code_start) + 1
            assert code_start != -1

            code_end: int = solution[::-1].index("```")
            assert code_start != -1

            # -4 = 3 backticks and also the \n before the backticks.
            code_end: int = len(solution) - 4 - code_end
            # +1 because of edge cases as in test_get_code_from_solution
            assert code_start <= code_end + 1

            solution = solution[code_start:code_end]
        except (ValueError, AssertionError):
            pass
        return solution

    def update_state(
        self, source_file: SourceFile, verifier_output: ESBMCOutput
    ) -> None:
        """Updates the latest state of the code and ESBMC output. It also updates
        the scenario, which is the type of error that ESBMC has shown. This should be
        called before generate_solution."""

        self.scenario = verifier_output.get_error_type()
        if not self.scenario:
            self.scenario = default_scenario

        self.source_code_raw = source_file.content

        # Format ESBMC output
        try:
            self.esbmc_output = replace(
                verifier_output,
                output=apply_formatting(
                    esbmc_output=verifier_output,
                    format=self.esbmc_output_type,
                ),
            )
        except SourceCodeParseError:
            # When clang output is displayed, show it entirely as it doesn't get very
            # big.
            self.esbmc_output = verifier_output

    def generate_solution(self, override_scenario: str | None = None) -> str:
        """Prompts the LLM to repair the source code using the verifier output.
        If this is the first time the method is called, the system message will
        be sent to the LLM. Then the initial prompt will be sent.

        In subsequent invokations of generate_solution, the initial prompt will
        be used only.

        So the system messages and initial message should each include at least
        {source_code} and {esbmc_output} so that they are substituted into the
        message.

        Queries the AI model to get a solution. Accepts an override scenario
        parameter, in which case the scenario won't be resolved automatically."""

        assert (
            self.source_code_raw is not None
            and self.esbmc_output is not None
            and self.scenario is not None
        ), "Call update_state before calling generate_solution."

        scenario: FixCodeScenario = self.scenarios[override_scenario or self.scenario]
        new_templates: list[MessageLikeRepresentation] = []

        # Apply system message if first cycle
        if self.invokations == 0:
            new_templates.extend(scenario.system)

        # Get scenario initial message and push it to message stack
        new_templates.append(HumanMessage(content=scenario.initial))
        # Prepare template values
        key_template_renderer: KeyTemplateRenderer = KeyTemplateRenderer(
            new_templates, self.template_key_provider
        )
        error_type: str | None = self.esbmc_output.get_error_type()
        self.messages.extend(
            key_template_renderer.format_messages(
                source_code=self.source_code,
                esbmc_output=self.esbmc_output.output,
                error_line=str(self.esbmc_output.get_error_line()),
                error_type=error_type if error_type else "unknown error",
            )
        )

        self.invokations += 1

        # Generate the solution
        response: BaseMessage = self.ai_model.invoke(self.messages)
        solution = SolutionGenerator.extract_code_from_solution(str(response.content))

        return solution
