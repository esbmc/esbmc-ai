# Author: Yiannis Charalambous

from abc import abstractmethod
from langchain.base_language import BaseLanguageModel

from langchain.callbacks import get_openai_callback
from langchain.llms.base import BaseLLM
from langchain.prompts import (
    HumanMessagePromptTemplate,
)
from langchain.prompts.chat import ChatPromptValue
from langchain.schema import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    LLMResult,
)

from .chat_response import ChatResponse, FinishReason
from .ai_models import AIModel


class BaseChatInterface(object):
    protected_messages: list[BaseMessage]
    messages: list[BaseMessage]
    ai_model: AIModel
    llm: BaseLanguageModel

    # TODO Consider removing ai_model from constructor.
    def __init__(
        self,
        system_messages: list[BaseMessage],
        llm: BaseLanguageModel,
        ai_model: AIModel,
    ) -> None:
        super().__init__()
        self.ai_model = ai_model

        self.protected_messages = system_messages.copy()
        self.messages = system_messages.copy()

        self.llm = llm

    @abstractmethod
    def compress_message_stack(self) -> None:
        raise NotImplementedError()

    def push_to_message_stack(
        self, message: BaseMessage, protected: bool = False
    ) -> None:
        if protected:
            self.protected_messages.append(message)
        self.messages.append(message)

    # Returns an OpenAI object back.
    def send_message(self, message: str, protected: bool = False) -> ChatResponse:
        """Sends a message to the AI model. Returns solution."""
        self.push_to_message_stack(
            message=HumanMessage(content=message),
            protected=protected,
        )

        # Transform message stack to ChatPromptValue

        message_prompts: ChatPromptValue
        if isinstance(self.llm, BaseLLM):
            # Load the LLM prompts.
            message_prompts = self.load_llm_template()
        else:
            # Is BaseChatModel so can use messages as is.
            message_prompts = ChatPromptValue(messages=self.messages)

        # TODO Add error checking back as it was before the LangChain update.

        # TODO When token counting comes to other models, implement it.

        response: ChatResponse
        with get_openai_callback() as cb:
            result: LLMResult = self.llm.generate_prompt(
                prompts=[message_prompts],
            )

            response_message: BaseMessage = AIMessage(
                content=result.generations[0][0].text
            )

            self.push_to_message_stack(message=response_message, protected=protected)

            response = ChatResponse(
                finish_reason=FinishReason.stop,
                message=response_message,
                total_tokens=cb.total_tokens,
            )

        return response

    # TODO FIXME Temporary place for this.
    def load_llm_template(self) -> ChatPromptValue:
        # Special tokens from: https://huggingface.co/tiiuae/falcon-7b-instruct/blob/main/special_tokens_map.json
        sys_initial_text: str = """>>DOMAIN<<You are a helpful assistant that answers any questions asked based on the previous messages in the conversation. The questions are asked by Human. The \"AI\" is the assistant. The AI shall not impersonate any other entity in the interaction including System and Human. The Human may refer to the AI directly, the AI should refer to the Human directly back, for example, when asked \"How do you suggest a fix?\", the AI shall respond \"You can try...\". The AI should follow the instructions given by System."""

        system_messages: list[BaseMessage] = [
            # sys_initial_text
            ChatMessage(role="", content=sys_initial_text),
            *self.messages[:-1],
        ]

        prompt_answer_template_text = """>>QUESTION<<{user_prompt}\n>>ANSWER<<"""

        prompt_answer_template = HumanMessagePromptTemplate.from_template(
            template=prompt_answer_template_text,
        )

        message_prompts: ChatPromptValue = ChatPromptValue(
            messages=[
                *system_messages,
                *prompt_answer_template.format_messages(user_prompt=self.messages[-1]),
            ]
        )

        return message_prompts
