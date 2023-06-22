# Author: Yiannis Charalambous

from typing import NamedTuple
from tiktoken import get_encoding, encoding_for_model

from .chat_api.chat_api import ChatAPI


class AIModel(NamedTuple):
    name: str = ""
    tokens: int = 0


AI_MODEL_GPT3 = AIModel("gpt-3.5-turbo", 4096)
AI_MODEL_GPT3_16K = AIModel("gpt-3.5-turbo-16k", 16384)
AI_MODEL_GPT4 = AIModel("gpt-4", 8192)
AI_MODEL_GPT4_32k = AIModel("gpt-4-32k", 32768)

# TODO Make it dynamically set from config.
AI_MODEL_TEXTGEN = AIModel("text-generation-inference", 8192)

models: list[AIModel] = [
    AI_MODEL_GPT3,
    AI_MODEL_GPT3_16K,
    AI_MODEL_GPT4,
    AI_MODEL_GPT4_32k,
    AI_MODEL_TEXTGEN,
]


def is_valid_ai_model(name: str) -> bool:
    for model in models:
        if model.name == name:
            return True
    return False


def num_tokens_from_messages(messages, model: AIModel):
    """Returns the number of tokens used by a list of messages.
    Source: https://platform.openai.com/docs/guides/chat/introduction"""
    model_name: str = model.name
    try:
        encoding = encoding_for_model(model_name)
    except KeyError:
        encoding = get_encoding("cl100k_base")

    # note: future models may deviate from this
    if is_valid_ai_model(model.name):
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
