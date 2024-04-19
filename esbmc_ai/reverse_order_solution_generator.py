# Author: Yiannis Charalambous

from langchain.schema import BaseMessage, HumanMessage
from typing_extensions import override, Optional
from esbmc_ai.solution_generator import (
    SolutionGenerator,
    get_source_code_formatted,
    get_source_code_err_line_idx,
    get_clang_err_line_index,
    apply_line_patch,
)
from esbmc_ai.chat_response import FinishReason, ChatResponse

# TODO Test me


class ReverseOrderSolutionGenerator(SolutionGenerator):
    """SolutionGenerator that shows the source code and verifier output state in
    reverse order."""

    @override
    def generate_solution(self) -> tuple[str, FinishReason]:
        self.push_to_message_stack(
            HumanMessage(content=self.ai_model_agent.initial_prompt)
        )

        # Format source code
        source_code_formatted: str = get_source_code_formatted(
            source_code_format=self.source_code_format,
            source_code=self.source_code_raw,
            esbmc_output=self.esbmc_output,
        )

        # Apply template substitution to message stack
        self.apply_template_value(
            source_code=source_code_formatted,
            esbmc_output=self.esbmc_output,
        )

        # Reverse the messages
        messages: list[BaseMessage] = self.messages.copy()
        self.messages.reverse()

        # Generate the solution
        response: ChatResponse = self.send_message()

        # Add to the reversed message the new message received by the LLM.
        messages.append(self.messages[-1])
        # Restore
        self.messages = messages

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
