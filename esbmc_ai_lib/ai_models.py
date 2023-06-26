# Author: Yiannis Charalambous

from typing import NamedTuple, Union
from enum import Enum


class AIModelProvider(Enum):
    """Specifies the interface used to communicate with the LLM."""

    open_ai = "openai"
    text_inference_server = "text_inference_server"


class AIModel(NamedTuple):
    name: str
    tokens: int
    provider: AIModelProvider
    # Below are only used for models that need them, such as models that
    # are using the provider "text_inference_server".
    url: str = ""
    config_message: str = ""


class AIModels(Enum):
    gpt_3 = AIModel("gpt-3.5-turbo", 4096, AIModelProvider.open_ai)
    gpt_3_16k = AIModel("gpt-3.5-turbo-16k", 16384, AIModelProvider.open_ai)
    gpt_4 = AIModel("gpt-4", 8192, AIModelProvider.open_ai)
    gpt_4_32k = AIModel("gpt-4-32k", 32768, AIModelProvider.open_ai)
    falcon_7b = AIModel(
        name="falcon-7b",
        tokens=8192,
        provider=AIModelProvider.text_inference_server,
        url="https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct",
        config_message='>>DOMAIN<<You are a helpful assistant that answers any questions asked based on the previous messages in the conversation. The questions are asked by Human. The "AI" is the assistant. The AI shall not impersonate any other entity in the interaction including System and Human. The Human may refer to the AI directly, the AI should refer to the Human directly back, for example, when asked "How do you suggest a fix?", the AI shall respond "You can try...". The AI should follow the instructions given by System.\n>>SUMMARY<<\n{history}\n>>QUESTION<<{user_prompt}\n>>ANSWER<<',
    )


_custom_ai_models: list[AIModel] = []

_ai_model_names: set[str] = set(item.value.name for item in AIModels)


def add_custom_ai_model(ai_model: AIModel) -> None:
    """Registers a custom AI model."""
    # Check if AI already already exists.
    if ai_model.name in _ai_model_names:
        raise Exception(f'AI Model "{ai_model.name}" already exists...')
    _ai_model_names.add(ai_model.name)
    _custom_ai_models.append(ai_model)


def is_valid_ai_model(ai_model: Union[str, AIModel]) -> bool:
    """Accepts both the AIModel object and the name as parameter."""
    name: str
    if isinstance(ai_model, AIModel):
        name = ai_model.name
    else:
        name = ai_model
    return name in _ai_model_names


def get_ai_model_by_name(name: str) -> AIModel:
    # Check AIModels enum.
    for enum_value in AIModels:
        ai_model: AIModel = enum_value.value
        if name == ai_model.name:
            return ai_model

    # Check custom AI models.
    for custom_ai in _custom_ai_models:
        if name == custom_ai.name:
            return custom_ai

    raise Exception(f'The AI "{name}" was not found...')
