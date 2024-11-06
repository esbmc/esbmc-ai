# Author: Yiannis Charalambous

"""Contains code for the base class for interacting with the LLMs in a 
conversation-based way."""

from abc import abstractmethod
from typing import Optional
import traceback

from langchain.schema import (
    BaseMessage,
    HumanMessage,
    PromptValue,
)
from langchain_core.language_models import BaseChatModel

from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.ai_models import AIModel


class BaseChatInterface:
    """Base class for interacting with an LLM. It allows for interactions with
    text generation LLMs and also chat LLMs."""

    def __init__(
        self,
        system_messages: list[BaseMessage],
        llm: BaseChatModel,
        ai_model: AIModel,
    ) -> None:
        super().__init__()
        self.ai_model: AIModel = ai_model
        self._system_messages: list[BaseMessage] = system_messages
        self.messages: list[BaseMessage] = []
        self.llm: BaseChatModel = llm

    @abstractmethod
    def compress_message_stack(self) -> None:
        """Compress the message stack, is abstract and needs to be implemented."""
        raise NotImplementedError()

    def push_to_message_stack(
        self,
        message: BaseMessage | tuple[BaseMessage, ...] | list[BaseMessage],
    ) -> None:
        """Pushes a message(s) to the message stack without querying the LLM."""
        if isinstance(message, list) or isinstance(message, tuple):
            self.messages.extend(list(message))
        else:
            self.messages.append(message)

    def apply_template_value(self, **kwargs: str) -> None:
        """Will substitute an f-string in the message stack and system messages to
        the provided value. The new substituted messages will become the new
        message stack, so the substitution is permanent."""

        system_message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self._system_messages,
            **kwargs,
        )
        self._system_messages = system_message_prompts.to_messages()

        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self.messages,
            **kwargs,
        )
        self.messages = message_prompts.to_messages()

    def get_applied_messages(self, **kwargs: str) -> tuple[BaseMessage, ...]:
        """Applies the f-string substituion and returns the result instead of assigning
        it to the message stack."""
        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self.messages,
            **kwargs,
        )
        return tuple(message_prompts.to_messages())

    def get_applied_system_messages(self, **kwargs: str) -> tuple[BaseMessage, ...]:
        """Same as `get_applied_messages` but for system messages."""
        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self._system_messages,
            **kwargs,
        )
        return tuple(message_prompts.to_messages())

    def send_message(self, message: Optional[str] = None) -> ChatResponse:
        """Sends a message to the AI model. Returns solution."""
        if message:
            self.push_to_message_stack(message=HumanMessage(content=message))

        all_messages = self._system_messages.copy()
        all_messages.extend(self.messages.copy())

        response_message: BaseMessage = self.llm.invoke(input=all_messages)

        self.push_to_message_stack(message=response_message)

        # Check if token limit has been exceeded.
        all_messages.append(response_message)
        new_tokens: int = self.llm.get_num_tokens_from_messages(
            messages=all_messages,
        )

        response: ChatResponse
        if new_tokens > self.ai_model.tokens:
            response = ChatResponse(
                finish_reason=FinishReason.length,
                message=response_message,
                total_tokens=self.ai_model.tokens,
            )
        else:
            response = ChatResponse(
                finish_reason=FinishReason.stop,
                message=response_message,
                total_tokens=new_tokens,
            )

        return response
