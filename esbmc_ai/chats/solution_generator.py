# Author: Yiannis Charalambous 2023

"""Contains code for automatically repairing code using ESBMC."""

from langchain_core.prompts import PromptTemplate
from langchain_core.prompts.chat import MessageLikeRepresentation
from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel

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
from esbmc_ai.chats import KeyTemplateRenderer


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
            value: str | None = esbmc_output.sections.violated_property
            if not value:
                raise ValueError("Not found violated property." + esbmc_output.output)
            return value
        case "ce":
            value: str | None = esbmc_output.sections.counterexample
            if not value:
                raise ValueError("Not found counterexample.")
            return value
        case "full":
            return esbmc_output.output
        case _:
            raise ValueError(f"Not a valid ESBMC output type: {format}")


class SolutionGenerator:
    """SolutionGenerator is a simple conversation-based automated program repair
    class. It maintains a conversation with the LLM, starting with a system message
    (provided at initialization) and then adding repair attempt messages via
    generate_solution calls."""

    def __init__(
        self,
        ai_model: BaseChatModel,
        esbmc_output_type: str = "full",
        system_message: list[BaseMessage] | None = None,
    ) -> None:
        """Initializes the solution generator."""
        super().__init__()

        self.ai_model: BaseChatModel = ai_model
        self.template_key_provider: TemplateKeyProvider = ESBMCTemplateKeyProvider()
        self.messages: list[BaseMessage] = system_message or []

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

    def generate_solution(
        self,
        initial_message_prompt: PromptTemplate,
        source_file: SourceFile,
        verifier_output: ESBMCOutput,
    ) -> str:
        """Prompts the LLM to repair the source code using the verifier output.
        Returns the extracted code from the LLM's response."""

        self.source_code = source_file

        # Format ESBMC output
        try:
            self.esbmc_output = verifier_output.model_copy(
                update={
                    "output": apply_formatting(
                        esbmc_output=verifier_output,
                        format=self.esbmc_output_type,
                    )
                }
            )
        except SourceCodeParseError:
            # When clang output is displayed, show it entirely as it doesn't get very
            # big.
            self.esbmc_output = verifier_output

        # Add the initial message for this repair attempt
        # Pass the template string to KeyTemplateRenderer which will handle formatting
        key_template_renderer: KeyTemplateRenderer = KeyTemplateRenderer(
            messages=[("human", initial_message_prompt.template)],
            key_provider=self.template_key_provider,
        )

        # Format with the current source code and ESBMC output
        formatted_messages = key_template_renderer.format_messages(
            source_code=source_file.content,
            esbmc_output=self.esbmc_output,
        )
        self.messages.extend(formatted_messages)

        self.invokations += 1

        # Generate the solution
        response: BaseMessage = self.ai_model.invoke(self.messages)
        solution = SolutionGenerator.extract_code_from_solution(str(response.content))

        return solution
