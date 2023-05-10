# Author: Yiannis Charalambous 2023

from src.base_chat_interface import BaseChatInterface


class ChatInterface(BaseChatInterface):
    solution: str = ""

    def __init__(self, system_messages: list, model: str, temperature: float) -> None:
        super().__init__(
            system_messages=system_messages,
            model=model,
            temperature=temperature,
        )

    def set_solution(self, source_code: str) -> None:
        """Sets the solution to the problem ESBMC reported, this will inform the AI."""
        self.solution = source_code
        self.push_to_message_stack(
            "user",
            f"Here is the corrected code:\n\n{source_code}",
        )
        self.push_to_message_stack("assistant", "Understood.")
