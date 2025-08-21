# Author: Yiannis Charalambous

"""Contains code for the base class for interacting with the LLMs in a 
conversation-based way."""

from time import sleep, time
from typing import Any, Optional, Sequence

from langchain.schema import (
    BaseMessage,
    HumanMessage,
    PromptValue,
)
import structlog

from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.ai_models import AIModel
from esbmc_ai.log_utils import LogCategories
from esbmc_ai.chats.template_key_provider import TemplateKeyProvider, GenericTemplateKeyProvider


class BaseChatInterface:
    """Base class for interacting with an LLM. It allows for interactions with
    text generation LLMs and also chat LLMs."""

    _last_attempt: float = 0
    cooldown_total: float = 20.0

    def __init__(
        self,
        system_messages: list[BaseMessage],
        ai_model: AIModel,
        template_key_provider: Optional[TemplateKeyProvider] = None,
    ) -> None:
        super().__init__()
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(
            category=LogCategories.CHAT
        )
        self.ai_model: AIModel = ai_model
        self._system_messages: list[BaseMessage] = system_messages
        self.messages: list[BaseMessage] = []
        self._template_key_provider = template_key_provider or GenericTemplateKeyProvider()

    def compress_message_stack(self) -> None:
        """Compress the message stack, is abstract and needs to be implemented."""
        self.messages = []

    def push_to_message_stack(
        self,
        message: BaseMessage | tuple[BaseMessage, ...] | list[BaseMessage],
    ) -> None:
        """Pushes a message(s) to the message stack without querying the LLM."""
        assert isinstance(message, BaseMessage | Sequence)
        if isinstance(message, Sequence):
            for m in message:
                assert isinstance(m, BaseMessage)
        if isinstance(message, list) or isinstance(message, tuple):
            self.messages.extend(list(message))
        else:
            self.messages.append(message)

    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Gets template keys for applying in template values using the configured provider."""
        return self._template_key_provider.get_template_keys(**kwargs)

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

    @staticmethod
    def send_messages(
        ai_model: AIModel,
        messages: list[BaseMessage],
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> ChatResponse:
        """Static method to send messages."""

        # Check cooldown
        time_passed: float = time() - BaseChatInterface._last_attempt
        if time_passed < BaseChatInterface.cooldown_total:
            sleep_total_seconds: float = BaseChatInterface.cooldown_total - time_passed
            if logger:
                logger.info(f"Sleeping for {sleep_total_seconds}...")
            sleep(sleep_total_seconds)
        BaseChatInterface._last_attempt = time()

        response_message: BaseMessage = ai_model.invoke(input=messages)

        # Check if token limit has been exceeded.
        new_tokens: int = ai_model.get_num_tokens_from_messages(
            messages=messages + [response_message],
        )

        response: ChatResponse
        if new_tokens > ai_model.tokens:
            response = ChatResponse(
                finish_reason=FinishReason.length,
                message=response_message,
                total_tokens=ai_model.tokens,
            )
        else:
            response = ChatResponse(
                finish_reason=FinishReason.stop,
                message=response_message,
                total_tokens=new_tokens,
            )

        return response

    def send_message(self, message: Optional[str] = None) -> ChatResponse:
        """Sends a message to the AI model. Returns solution."""
        if message:
            self.push_to_message_stack(message=HumanMessage(content=message))

        all_messages = self._system_messages.copy()
        all_messages.extend(self.messages.copy())

        if message:
            self._logger.debug(f"LLM Prompt: {message}")

        response: ChatResponse = self.send_messages(
            ai_model=self.ai_model,
            messages=all_messages,
            logger=self._logger,
        )

        self._logger.debug(f"LLM Response: {response.message.content}")

        self.push_to_message_stack(message=response.message)
        return response
