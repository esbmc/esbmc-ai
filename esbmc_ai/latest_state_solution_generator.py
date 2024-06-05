# Author: Yiannis Charalambous

from typing_extensions import override
from langchain_core.messages import BaseMessage
from esbmc_ai.solution_generator import SolutionGenerator
from esbmc_ai.chat_response import FinishReason

# TODO Test me


class LatestStateSolutionGenerator(SolutionGenerator):
    """SolutionGenerator that only shows the latest source code and verifier
    output state."""

    @override
    def generate_solution(self) -> tuple[str, FinishReason]:
        # Backup message stack and clear before sending base message. We want
        # to keep the message stack intact because we will print it with
        # print_raw_conversation.
        messages: list[BaseMessage] = self.messages
        self.messages: list[BaseMessage] = []
        solution, finish_reason = super().generate_solution()
        # Append last messages to the messages stack
        messages.extend(self.messages)
        # Restore
        self.messages = messages
        return solution, finish_reason
