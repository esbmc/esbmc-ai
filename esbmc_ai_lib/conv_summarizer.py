# Author: Yiannis Charalambous

from esbmc_ai_lib.ai_models import AIModel
from .base_chat_interface import BaseChatInterface, ChatResponse


class ConversationSummarizerChat(BaseChatInterface):

    """# ConversationSummarizerChat
    AI Chat that will summarize conversations and return a compressed summmary.
    This is primarily used by `ChatInterface`."""

    def __init__(
        self,
        system_messages: list,
        ai_model: AIModel,
        temperature: float,
    ) -> None:
        super().__init__(
            system_messages,
            ai_model=ai_model,
            temperature=temperature,
        )

    def compress_message_stack(self) -> None:
        """No need to implement a compression method."""
        raise NotImplementedError()

    def summarize_messages(self, messages: list) -> ChatResponse:
        """Summarizes the provided messages into a much smaller block. This is
        done by combining all messages into one string and asking the
        ConversationSummarizerChat to give a summary. The message stack is
        cleared upon calling this function automatically."""
        # Clear chat.
        self.messages = self.protected_messages
        # Create a natural language chat interace.
        message_str: str = "\n\n".join(
            [f"{message['role']}:\n{message['content']}" for message in messages]
        )

        self.push_to_message_stack(
            "user",
            "Reply OK if you understand that the following text is the conversation:\n\n"
            + message_str,
        )
        self.push_to_message_stack("assistant", "OK.")
        result: ChatResponse = self.send_message(
            "Summarize the provided conversations."
        )
        return result
