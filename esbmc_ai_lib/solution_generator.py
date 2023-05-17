# Author: Yiannis Charalambous 2023

from .base_chat_interface import ChatResponse
from .user_chat import ChatInterface


class SolutionGenerator(ChatInterface):
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
        self.initial_prompt = initial_prompt
        self.esbmc_output = esbmc_output

        # Introduce source code and ESBMC output to AI.
        self.push_to_message_stack(
            "user",
            f"The following text is the source code of the program, reply OK if you understand:\n\n{source_code}",
        )
        self.push_to_message_stack("assistant", "ok")
        self.push_to_message_stack(
            "user",
            f"The following text is the output of ESBMC, reply OK if you understand:\n\n{esbmc_output}",
        )
        self.push_to_message_stack("assistant", "ok")

    def compress_message_stack(self) -> None:
        # TODO Delete previous and system messages.

        return super().compress_message_stack()

    def generate_solution(self) -> str:
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

        return solution
