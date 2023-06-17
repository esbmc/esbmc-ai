# Author: Yiannis Charalambous

from .base_chat_interface import BaseChatInterface, ChatResponse
from .ai_models import AIModel


class OptimizeCode(BaseChatInterface):
    initial_message: str

    def __init__(
        self,
        system_messages: list,
        initial_message: str,
        ai_model: AIModel,
        temperature: float,
    ) -> None:
        super().__init__(system_messages, ai_model=ai_model, temperature=temperature)

        self.initial_message = initial_message

    def optimize_function(self, source_code: str, function_name: str) -> ChatResponse:
        self.messages = self.protected_messages.copy()
        self.push_to_message_stack(
            "user",
            f"Reply OK if you understand the following is the source code to optimize:\n\n{source_code}",
            True,
        )
        self.push_to_message_stack("assistant", "OK.", True)

        expanded_initial_message: str = self.initial_message.replace(
            "%s", function_name
        )
        return self.send_message(expanded_initial_message)
