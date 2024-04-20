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
    def send_message(self, message: Optional[str] = None) -> ChatResponse:
        # Reverse the messages
        messages: list[BaseMessage] = self.messages.copy()
        self.messages.reverse()

        response: ChatResponse = super().send_message(message)

        # Add to the reversed message the new message received by the LLM.
        messages.append(self.messages[-1])
        # Restore
        self.messages = messages

        return response
