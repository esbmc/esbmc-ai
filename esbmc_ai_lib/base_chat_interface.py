# Author: Yiannis Charalambous

from abc import abstractmethod
from typing import NamedTuple
import openai

from .ai_models import AIModel, AI_MODEL_GPT3, num_tokens_from_messages


# API returned complete model output
FINISH_REASON_STOP: str = "stop"
# Incomplete model output due to max_tokens parameter or token limit
FINISH_REASON_LENGTH: str = "length"
# Omitted content due to a flag from our content filters
FINISH_REASON_CONTENT_FILTER: str = "content_filter"
# API response still in progress or incomplete
FINISH_REASON_NULL: str = "null"


class ChatResponse(NamedTuple):
    base_message: object = None
    finish_reason: str = FINISH_REASON_NULL
    role: str = ""
    message: str = ""
    total_tokens: int = 0


class BaseChatInterface(object):
    protected_messages: list
    messages: list
    ai_model: AIModel
    temperature: float

    def __init__(
        self,
        system_messages: list,
        ai_model: AIModel = AI_MODEL_GPT3,
        temperature: float = 1.0,
    ) -> None:
        super().__init__()
        self.ai_model = ai_model
        self.temperature = temperature

        self.protected_messages = system_messages.copy()
        self.messages = system_messages.copy()

    @abstractmethod
    def compress_message_stack(self) -> None:
        raise NotImplementedError()

    def push_to_message_stack(
        self, role: str, message: str, protected: bool = False
    ) -> None:
        message_struct = {"role": role, "content": message}
        if protected:
            self.protected_messages.append(message_struct)
        self.messages.append(message_struct)

    # Returns an OpenAI object back.
    def send_message(self, message: str, protected: bool = False) -> ChatResponse:
        """Sends a message to the AI model. Returns solution. If the message
        stack fills up, the command will exit with no changes to the message
        stack."""
        # See if the new stack if over the limit.
        new_stack = [*self.messages, {"role": "user", "content": message}]

        # Check if message is too long and exit.
        msg_tokens: int = num_tokens_from_messages(new_stack, self.ai_model)
        if msg_tokens > self.ai_model.tokens:
            response: ChatResponse = ChatResponse(
                finish_reason=FINISH_REASON_LENGTH,
            )
            return response

        completion = openai.ChatCompletion.create(
            model=self.ai_model.name,
            messages=new_stack,
            temperature=self.temperature,
        )

        response = ChatResponse(
            base_message=completion,
            role=completion.choices[0].message.role,
            message=completion.choices[0].message.content,
            finish_reason=completion.choices[0].finish_reason,
            total_tokens=completion.usage.total_tokens,
        )

        # If the response is OK then add to stack.
        if response.finish_reason == FINISH_REASON_STOP:
            self.push_to_message_stack("user", message, protected)
            self.push_to_message_stack(response.role, response.message, protected)

        return response
