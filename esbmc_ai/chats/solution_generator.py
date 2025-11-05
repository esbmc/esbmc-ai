# Author: Yiannis Charalambous 2023

"""Contains code for automatically repairing code using ESBMC."""

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel

from esbmc_ai.solution import SourceFile
from esbmc_ai.chats.template_key_provider import (
    ESBMCTemplateKeyProvider,
    TemplateKeyProvider,
)
from esbmc_ai.verifiers.esbmc import ESBMCOutput
from esbmc_ai.chats import KeyTemplateRenderer


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

        # Add AI response to message history for conversation context
        self.messages.append(response)

        solution = SolutionGenerator.extract_code_from_solution(str(response.content))

        return solution
