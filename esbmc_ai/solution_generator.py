# Author: Yiannis Charalambous 2023

from re import S
from typing import Optional
from typing_extensions import override
from langchain.base_language import BaseLanguageModel
from langchain.schema import BaseMessage, HumanMessage

from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.config import ChatPromptSettings, DynamicAIModelAgent
from esbmc_ai.frontend.solution import apply_line_patch

from .ai_models import AIModel
from .base_chat_interface import BaseChatInterface
from esbmc_ai.esbmc_util import (
    esbmc_get_counter_example,
    esbmc_get_violated_property,
    get_source_code_err_line_idx,
    get_clang_err_line_index,
)


class ESBMCTimedOutException(Exception):
    pass


class SourceCodeParseError(Exception):
    pass


def get_source_code_formatted(
    source_code_format: str, source_code: str, esbmc_output: str
) -> str:
    match source_code_format:
        case "single":
            # Get source code error line from esbmc output
            line: Optional[int] = get_source_code_err_line_idx(esbmc_output)
            if line:
                return source_code.splitlines(True)[line]

            # Check if it parses
            line = get_clang_err_line_index(esbmc_output)
            if line:
                return source_code.splitlines(True)[line]

            raise AssertionError(
                f"error line not found in esbmc output:\n{esbmc_output}"
            )
        case "full":
            return source_code
        case _:
            raise ValueError(
                f"Not a valid format for source code: {source_code_format}"
            )


def get_esbmc_output_formatted(esbmc_output_type: str, esbmc_output: str) -> str:
    # Check for parsing error
    if "ERROR: PARSING ERROR" in esbmc_output:
        # Parsing errors are usually small in nature.
        raise SourceCodeParseError()
    elif "ERROR: Timed out" in esbmc_output:
        raise ESBMCTimedOutException()

    match esbmc_output_type:
        case "vp":
            value: Optional[str] = esbmc_get_violated_property(esbmc_output)
            if not value:
                raise ValueError("Not found violated property." + esbmc_output)
            return value
        case "ce":
            value: Optional[str] = esbmc_get_counter_example(esbmc_output)
            if not value:
                raise ValueError("Not found counterexample.")
            return value
        case "full":
            return esbmc_output
        case _:
            raise ValueError(f"Not a valid ESBMC output type: {esbmc_output_type}")


class SolutionGenerator(BaseChatInterface):
    def __init__(
        self,
        ai_model_agent: DynamicAIModelAgent | ChatPromptSettings,
        llm: BaseLanguageModel,
        ai_model: AIModel,
        scenario: str = "",
        source_code_format: str = "full",
        esbmc_output_type: str = "full",
    ) -> None:
        """Initializes the solution generator. This ModelChat provides Dynamic
        Prompting. Will get the correct scenario from the DynamicAIModelAgent
        supplied and create a ChatPrompt."""

        chat_prompt: ChatPromptSettings = ai_model_agent
        if isinstance(ai_model_agent, DynamicAIModelAgent):
            # Convert to chat prompt
            chat_prompt = DynamicAIModelAgent.to_chat_prompt_settings(
                ai_model_agent=ai_model_agent, scenario=scenario
            )

        super().__init__(
            ai_model_agent=chat_prompt,
            ai_model=ai_model,
            llm=llm,
        )

        self.esbmc_output_type: str = esbmc_output_type
        self.source_code_format: str = source_code_format

        self.source_code_raw: Optional[str] = None
        self.source_code_formatted: Optional[str] = None
        self.esbmc_output: Optional[str] = None

    @override
    def compress_message_stack(self) -> None:
        # Resets the conversation - cannot summarize code
        # If generate_solution is called after this point, it will start new
        # with the currently set state.
        self.messages: list[BaseMessage] = []

    @classmethod
    def get_code_from_solution(cls, solution: str) -> str:
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

    def update_state(self, source_code: str, esbmc_output: str) -> None:
        """Updates the latest state of the code and ESBMC output. This should be
        called before generate_solution."""
        self.source_code_raw = source_code

        # Format ESBMC output
        try:
            self.esbmc_output = get_esbmc_output_formatted(
                esbmc_output_type=self.esbmc_output_type,
                esbmc_output=esbmc_output,
            )
        except SourceCodeParseError:
            # When clang output is displayed, show it entirely as it doesn't get very
            # big.
            self.esbmc_output = esbmc_output

        # Format source code
        self.source_code_formatted = get_source_code_formatted(
            source_code_format=self.source_code_format,
            source_code=source_code,
            esbmc_output=self.esbmc_output,
        )

    def generate_solution(self) -> tuple[str, FinishReason]:
        assert (
            self.source_code_raw is not None
            and self.source_code_formatted is not None
            and self.esbmc_output is not None
        ), "Call update_state before calling generate_solution."

        self.push_to_message_stack(
            HumanMessage(content=self.ai_model_agent.initial_prompt)
        )

        # Apply template substitution to message stack
        self.apply_template_value(
            source_code=self.source_code_formatted,
            esbmc_output=self.esbmc_output,
        )

        # Generate the solution
        response: ChatResponse = self.send_message()
        solution: str = str(response.message.content)

        solution = SolutionGenerator.get_code_from_solution(solution)

        # If source code passed to LLM is formatted then we need to recombine to
        # full source code before giving to ESBMC
        match self.source_code_format:
            case "single":
                # Get source code error line from esbmc output
                line: Optional[int] = get_source_code_err_line_idx(self.esbmc_output)
                if not line:
                    # Check if it parses
                    line = get_clang_err_line_index(self.esbmc_output)

                assert (
                    line
                ), "fix code command: error line could not be found to apply brutal patch replacement"
                solution = apply_line_patch(self.source_code_raw, solution, line, line)

        return solution, response.finish_reason
