# Author: Yiannis Charalambous 2023

from .base_chat_interface import BaseChatInterface, ChatResponse
from .user_chat import ChatInterface


class SolutionGenerator(BaseChatInterface):
    initial_prompt: str
    source_code: str
    esbmc_output: str

    def __init__(
        self,
        system_messages: list,
        initial_prompt: str,
        source_code: str,
        esbmc_output: str,
        model: str,
        temperature: float,
    ) -> None:
        super().__init__(
            system_messages=system_messages,
            model=model,
            temperature=temperature,
        )
        self.initial_prompt = initial_prompt
        self.source_code = source_code
        self.esbmc_output = esbmc_output

        # Introduce source code and ESBMC output to AI.
        self.push_to_message_stack(
            "user",
            f"The following text is the source code of the program, reply OK if you understand:\n\n{source_code}",
            True,
        )
        self.push_to_message_stack("assistant", "ok", True)
        self.push_to_message_stack(
            "user",
            f"The following text is the output of ESBMC, reply OK if you understand:\n\n{esbmc_output}",
            True,
        )
        self.push_to_message_stack("assistant", "ok", True)

    def compress_message_stack(self) -> None:
        self.messages = self.protected_messages.copy()

    def generate_solution(self) -> tuple[str, str]:
        response: ChatResponse = self.send_message(self.initial_prompt)
        solution: str = response.message

        # Strip the source code of any leftover text as sometimes the AI model
        # will generate text and formatting despite being told not to.
        try:
            code_start: int = solution.index("```") + 3
            code_end: int = len(solution) - 3 - solution[::-1].index("```")
            solution = solution[code_start:code_end]
        except ValueError:
            pass

        return solution, response.finish_reason
