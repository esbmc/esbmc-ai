# Author: Yiannis Charalambous

from langchain.base_language import BaseLanguageModel
from langchain.schema import AIMessage, BaseMessage, HumanMessage

from esbmc_ai.config import ChatPromptSettings
from .base_chat_interface import BaseChatInterface, ChatResponse
from .ai_models import AIModel


class OptimizeCode(BaseChatInterface):
    initial_message: str

    def __init__(
        self,
        ai_model_agent: ChatPromptSettings,
        initial_message: str,
        ai_model: AIModel,
        llm: BaseLanguageModel,
    ) -> None:
        super().__init__(ai_model_agent=ai_model_agent, ai_model=ai_model, llm=llm)

        self.initial_message = initial_message

    def optimize_function(self, source_code: str, function_name: str) -> ChatResponse:
        self.messages = []
        self.push_to_message_stack(
            HumanMessage(
                content=f"Reply OK if you understand the following is the source code to optimize:\n\n{source_code}"
            )
        )
        self.push_to_message_stack(AIMessage(content="OK."))

        expanded_initial_message: str = self.initial_message.replace(
            "%s", function_name
        )
        return self.send_message(expanded_initial_message)
