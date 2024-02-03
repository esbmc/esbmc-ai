# Author: Yiannis Charalambous 2023

from typing_extensions import override

from langchain.base_language import BaseLanguageModel
from langchain.memory import ConversationSummaryMemory, ChatMessageHistory
from langchain.schema import BaseMessage, PromptValue, SystemMessage

from esbmc_ai.config import AIAgentConversation, ChatPromptSettings

from .ai_models import AIModel
from .base_chat_interface import BaseChatInterface


class UserChat(BaseChatInterface):
    solution: str = ""

    def __init__(
        self,
        ai_model_agent: ChatPromptSettings,
        ai_model: AIModel,
        llm: BaseLanguageModel,
        source_code: str,
        esbmc_output: str,
        set_solution_messages: AIAgentConversation,
    ) -> None:
        super().__init__(
            ai_model_agent=ai_model_agent,
            ai_model=ai_model,
            llm=llm,
        )

        # Store source code and esbmc output in order to substitute it into the message stack.
        self.source_code: str = source_code
        self.esbmc_output: str = esbmc_output
        # The messsages for setting a new solution to the source code.
        self.set_solution_messages = set_solution_messages

        self.set_template_value("source_code", self.source_code)
        self.set_template_value("esbmc_output", self.esbmc_output)

    def set_solution(self, source_code: str) -> None:
        """Sets the solution to the problem ESBMC reported, this will inform the AI."""

        self.set_template_value("source_code_solution", source_code)

        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self.set_solution_messages.messages,
            **self.template_values,
        )

        for message in message_prompts.to_messages():
            self.push_to_message_stack(message)

    def set_optimized_solution(self, source_code: str) -> None:
        # NOTE Here we use the same system message as `set_solution`.
        self.set_template_value("source_code_solution", source_code)

        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=self.set_solution_messages.messages,
            **self.template_values,
        )

        for message in message_prompts.to_messages():
            self.push_to_message_stack(message)

    @override
    def compress_message_stack(self) -> None:
        """Uses ConversationSummaryMemory from Langchain to summarize the conversation of all the non-protected
        messages into one summary message which is added into the conversation as a SystemMessage.
        """

        memory: ConversationSummaryMemory = ConversationSummaryMemory.from_messages(
            llm=self.llm,
            chat_memory=ChatMessageHistory(messages=self.messages),
        )

        self.messages: list[BaseMessage] = []

        self.push_to_message_stack(SystemMessage(content=memory.buffer))
