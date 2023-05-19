# Author: Yiannis Charalambous 2023

from .base_chat_interface import BaseChatInterface, ChatResponse
from .conv_summarizer import ConversationSummarizerChat


class ChatInterface(BaseChatInterface):
    solution: str = ""
    summarizer: ConversationSummarizerChat

    def __init__(
        self,
        system_messages: list,
        model: str,
        temperature: float,
        summarizer: ConversationSummarizerChat,
    ) -> None:
        super().__init__(
            system_messages=system_messages,
            model=model,
            temperature=temperature,
        )
        self.summarizer = summarizer

    def set_solution(self, source_code: str) -> None:
        """Sets the solution to the problem ESBMC reported, this will inform the AI."""
        self.solution = source_code
        self.push_to_message_stack(
            "user",
            f"Here is the corrected code:\n\n{source_code}",
            True,
        )
        self.push_to_message_stack("assistant", "Understood.", True)

    def compress_message_stack(self) -> None:
        # Reset chat to essentials.
        self.messages = self.protected_messages.copy()

        # Get all non protected messages.
        unprotected_messages: list = self.messages[len(self.protected_messages) :]
        result: ChatResponse = self.summarizer.summarize_messages(unprotected_messages)
        # Let AI model know that this is the summary of the compressed conversation.
        self.push_to_message_stack(
            "user",
            "Here is a summary of the previous conversation:\n\n" + result.message,
        )
        self.push_to_message_stack(
            "assistant",
            "Understood, I will use this conversation as a basis for future queries.",
        )
