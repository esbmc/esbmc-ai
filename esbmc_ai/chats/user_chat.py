# Author: Yiannis Charalambous 2023

"""Contains class that handles the UserChat of ESBMC-AI"""

from typing import Optional
from typing_extensions import override

from langchain.memory import ConversationSummaryMemory
from langchain.schema import BaseMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_community.chat_message_histories import ChatMessageHistory


from esbmc_ai.ai_models import AIModel
from esbmc_ai.solution import Solution
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.chats.base_chat_interface import BaseChatInterface


class UserChat(BaseChatInterface):
    """Simple interface that talks to the LLM and stores the result. The class
    also stores the fixed results from fix code command."""

    def __init__(
        self,
        ai_model: AIModel,
        llm: BaseChatModel,
        solution: Solution,
        esbmc_output: VerifierOutput,
        system_messages: list[BaseMessage],
        set_solution_messages: list[BaseMessage],
    ) -> None:
        super().__init__(
            system_messages=system_messages,
            ai_model=ai_model,
            llm=llm,
        )
        # Store source code and esbmc output in order to substitute it into the message stack.
        self.solution: Solution = solution
        self.esbmc_output: VerifierOutput = esbmc_output
        # The messsages for setting a new solution to the source code.
        self.set_solution_messages = set_solution_messages

        error_type: Optional[str] = self.esbmc_output.get_error_type()

        self.apply_template_value(
            **self.get_canonical_template_keys(
                source_code=self.solution.files[0].content,
                esbmc_output=self.esbmc_output.output,
                error_line=str(self.esbmc_output.get_error_line()),
                error_type=error_type if error_type else "unknown error",
            )
        )

    def set_solution(self, source_code: str) -> None:
        """Sets the solution to the problem ESBMC reported, this will inform the AI."""

        for msg in self.set_solution_messages:
            self.push_to_message_stack(msg)

        self.apply_template_value(source_code_solution=source_code)

    @override
    def compress_message_stack(self) -> None:
        """Uses ConversationSummaryMemory from Langchain to summarize the
        conversation of all the non-protected messages into one summary message
        which is added into the conversation as a SystemMessage.
        """

        memory: ConversationSummaryMemory = ConversationSummaryMemory.from_messages(
            llm=self.llm,
            chat_memory=ChatMessageHistory(messages=self.messages),
        )

        self.messages: list[BaseMessage] = []

        self.push_to_message_stack(SystemMessage(content=memory.buffer))
