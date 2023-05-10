# Author: Yiannis Charalambous

import openai
from tiktoken import get_encoding, encoding_for_model

from src.ai_models import AI_MODEL_GPT3, AI_MODEL_GPT4

MAX_TOKENS_GPT3TURBO: int = 4096


def num_tokens_from_messages(messages, model=AI_MODEL_GPT3):
    """Returns the number of tokens used by a list of messages.
    Source: https://platform.openai.com/docs/guides/chat/introduction"""
    try:
        encoding = encoding_for_model(model)
    except KeyError:
        encoding = get_encoding("cl100k_base")
    # note: future models may deviate from this
    if model.startswith(AI_MODEL_GPT3) or model.startswith(AI_MODEL_GPT4):
        num_tokens = 0
        for message in messages:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                # if there's a name, the role is omitted
                if key == "name":
                    # role is always required and always 1 token
                    num_tokens += -1
        # every reply is primed with <im_start>assistant
        num_tokens += 2
        return num_tokens
    else:
        # See https://github.com/openai/openai-python/blob/main/chatml.md for
        # information on how messages are converted to tokens.
        raise NotImplementedError(
            f"num_tokens_from_messages() is not presently implemented for model {model}."
        )


class BaseChatInterface(object):
    max_tokens = MAX_TOKENS_GPT3TURBO

    system_messages: list
    messages: list
    model_name: str
    temperature: float

    def __init__(
        self,
        system_messages: list,
        model: str = "gpt-3.5-turbo",
        temperature: float = 1.0,
    ) -> None:
        super().__init__()
        self.system_messages = system_messages
        self.messages = self.system_messages
        self.model_name = model
        self.temperature = temperature

    def push_to_message_stack(self, role: str, message: str) -> None:
        self.messages.append({"role": role, "content": message})

    # Returns an OpenAI object back.
    def send_message(self, message: str):
        self.push_to_message_stack("user", message)

        # Check if necessary to shorten.
        msg_tokens: int = num_tokens_from_messages(self.messages, self.model_name)
        if msg_tokens > self.max_tokens:
            print(
                f"Max tokens reached... Conversation too long {msg_tokens}/{self.max_tokens}. Exiting..."
            )
            exit(2)

        completion = openai.ChatCompletion.create(
            model=self.model_name,
            messages=self.messages,
            temperature=self.temperature,
        )

        response_role = completion.choices[0].message.role
        response_message = completion.choices[0].message.content
        self.push_to_message_stack(response_role, response_message)

        return completion
