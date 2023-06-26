# Author: Yiannis Charalambous 2023

from typing_extensions import override
from langchain.base_language import BaseLanguageModel

from langchain.schema import AIMessage, HumanMessage, SystemMessage

from .ai_models import AIModel
from .base_chat_interface import BaseChatInterface


class ChatInterface(BaseChatInterface):
    solution: str = ""

    def __init__(
        self,
        system_messages: list,
        ai_model: AIModel,
        llm: BaseLanguageModel,
        source_code: str,
        esbmc_output: str,
    ) -> None:
        super().__init__(
            system_messages=system_messages,
            ai_model=ai_model,
            llm=llm,
        )

        self.push_to_message_stack(
            message=SystemMessage(
                content=f"Reply OK if you understand that the following text is the program source code:\n\n{source_code}"
            ),
            protected=True,
        )

        self.push_to_message_stack(message=AIMessage(content="OK"), protected=True)

        self.push_to_message_stack(
            message=SystemMessage(
                content=f"Reply OK if you understand that the following text is the output from ESBMC:\n\n{esbmc_output}",
            ),
            protected=True,
        )

        self.push_to_message_stack(message=AIMessage(content="OK"), protected=True)

    def set_solution(self, source_code: str) -> None:
        """Sets the solution to the problem ESBMC reported, this will inform the AI."""
        self.solution = source_code
        self.push_to_message_stack(
            message=HumanMessage(
                content=f"Here is the corrected code:\n\n{source_code}"
            ),
            protected=True,
        )

        self.push_to_message_stack(
            message=AIMessage(content="Understood"), protected=True
        )

    @override
    def compress_message_stack(self) -> None:
        raise NotImplementedError()
        # TODO
        # # Reset chat to essentials.
        # self.messages = self.protected_messages.copy()

        # # Get all non protected messages.
        # unprotected_messages: list = self.messages[len(self.protected_messages) :]
        # result: ChatResponse = self.summarizer.summarize_messages(unprotected_messages)
        # # Let AI model know that this is the summary of the compressed conversation.
        # self.push_to_message_stack(
        #     "user",
        #     "Here is a summary of the previous conversation:\n\n" + result.message,
        # )
        # self.push_to_message_stack(
        #     "assistant",
        #     "Understood, I will use this conversation as a basis for future queries.",
        # )
