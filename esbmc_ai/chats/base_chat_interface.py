# Author: Yiannis Charalambous

"""Contains code for the base class for interacting with the LLMs in a
conversation-based way."""

from typing import Any, Sequence

from langchain.schema import (
    BaseMessage,
    HumanMessage,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from esbmc_ai.chats.template_key_provider import (
    TemplateKeyProvider,
    GenericTemplateKeyProvider,
)


class BaseChatInterface:
    """Base class for interacting with an LLM. It allows for interactions with
    text generation LLMs and also chat LLMs."""

    def __init__(
        self,
        ai_model: BaseChatModel,
        system_messages: list[BaseMessage],
        template_key_provider: TemplateKeyProvider | None = None,
    ) -> None:
        super().__init__()
        self.ai_model: BaseChatModel = ai_model
        self._system_messages: list[BaseMessage] = system_messages
        self.messages: list[BaseMessage] = []
        self._template_key_provider = (
            template_key_provider or GenericTemplateKeyProvider()
        )

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

        # Create prompt templates and format messages
        system_prompt = ChatPromptTemplate.from_messages(self._system_messages)
        self._system_messages = system_prompt.format_messages(**kwargs)

        messages_prompt = ChatPromptTemplate.from_messages(self.messages)
        self.messages = messages_prompt.format_messages(**kwargs)

    def get_applied_messages(self, **kwargs: str) -> tuple[BaseMessage, ...]:
        """Applies the f-string substituion and returns the result instead of assigning
        it to the message stack."""
        messages_prompt = ChatPromptTemplate.from_messages(self.messages)
        return tuple(messages_prompt.format_messages(**kwargs))

    def get_applied_system_messages(self, **kwargs: str) -> tuple[BaseMessage, ...]:
        """Same as `get_applied_messages` but for system messages."""
        system_prompt = ChatPromptTemplate.from_messages(self._system_messages)
        return tuple(system_prompt.format_messages(**kwargs))

    def send_message(self, message: str | None = None) -> BaseMessage:
        """Sends a message to the AI model. Returns response message."""
        if message:
            self.push_to_message_stack(message=HumanMessage(content=message))

        all_messages = self._system_messages.copy()
        all_messages.extend(self.messages.copy())

        response_message: BaseMessage = self.ai_model.invoke(input=all_messages)

        self.push_to_message_stack(message=response_message)

        return response_message
