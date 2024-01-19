# Author: Yiannis Charalambous

from abc import abstractmethod

from langchain.base_language import BaseLanguageModel
from langchain_community.callbacks import get_openai_callback
from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    LLMResult,
    PromptValue,
)

from openai import InternalServerError

from .config import ChatPromptSettings
from .chat_response import ChatResponse, FinishReason
from .ai_models import AIModel, AIModelOpenAI


class BaseChatInterface(object):
    def __init__(
        self,
        ai_model_agent: ChatPromptSettings,
        llm: BaseLanguageModel,
        ai_model: AIModel,
    ) -> None:
        super().__init__()
        self.ai_model: AIModel = ai_model
        self.ai_model_agent: ChatPromptSettings = ai_model_agent
        self.messages: list[BaseMessage] = []
        self.llm: BaseLanguageModel = llm
        self.template_values: dict[str, str] = {}

    @abstractmethod
    def compress_message_stack(self) -> None:
        raise NotImplementedError()

    def set_template_value(self, key: str, value: str) -> None:
        """Replaces a template key with the value provided when the chat template is
        applied."""
        self.template_values[key] = value

    def push_to_message_stack(
        self,
        message: BaseMessage,
    ) -> None:
        self.messages.append(message)

    def send_message(self, message: str) -> ChatResponse:
        """Sends a message to the AI model. Returns solution."""
        self.push_to_message_stack(message=HumanMessage(content=message))

        messages = list(self.ai_model_agent.system_messages.messages)
        messages.extend(self.messages)

        # Transform message stack to ChatPromptValue: If this is a ChatLLM then the
        # function will simply be an identity function that does nothing and simply
        # returns the messages as a ChatPromptValue. If this is a text generation
        # LLM, then the function should inject the config message around the
        # conversation to make the LLM behave like a ChatLLM.
        message_prompts: PromptValue = self.ai_model.apply_chat_template(
            messages=messages,
            **self.template_values,
        )

        # TODO When token counting comes to other models, implement it.
        # Need to implement ai_model.tokens...

        response: ChatResponse
        with get_openai_callback() as cb:
            try:
                result: LLMResult = self.llm.generate_prompt(
                    prompts=[message_prompts],
                )

                response_message: BaseMessage = AIMessage(
                    content=result.generations[0][0].text
                )

                self.push_to_message_stack(message=response_message)

                response = ChatResponse(
                    finish_reason=FinishReason.stop,
                    message=response_message,
                    total_tokens=cb.total_tokens,
                )
            # FIXME
            # except TokenLimitExceededException as e:
            #     # HFTextGen
            #     response = ChatResponse(
            #         finish_reason=FinishReason.length,
            #         # NOTE Show the total tokens of the model instead of 0
            #         # (no token counting currently...)
            #         total_tokens=self.ai_model.tokens,
            #     )
            except InternalServerError as e:
                # OpenAI model error handling.
                if e.code == AIModelOpenAI.context_length_exceeded_error:
                    response = ChatResponse(
                        finish_reason=FinishReason.length,
                        total_tokens=cb.total_tokens,
                    )
                else:
                    raise
            except Exception as e:
                print(f"There was an unkown error when generating a response: {e}")
                exit(1)

        return response
