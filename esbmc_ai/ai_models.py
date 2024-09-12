# Author: Yiannis Charalambous

from abc import abstractmethod
from typing import Any, Iterable, Optional, Union
from enum import Enum
from langchain_core.language_models import BaseChatModel
from pydantic.v1.types import SecretStr
from typing_extensions import override

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from langchain.prompts.chat import ChatPromptTemplate
from langchain.schema import (
    BaseMessage,
    PromptValue,
)


from esbmc_ai.api_key_collection import APIKeyCollection


class AIModel(object):
    """This base class represents an abstract AI model."""

    name: str
    tokens: int

    def __init__(
        self,
        name: str,
        tokens: int,
    ) -> None:
        self.name = name
        self.tokens = tokens

    @abstractmethod
    def create_llm(
        self,
        api_keys: APIKeyCollection,
        temperature: float = 1.0,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        """Initializes a large language model model with the provided parameters."""
        raise NotImplementedError()

    @classmethod
    def convert_messages_to_tuples(
        cls, messages: Iterable[BaseMessage]
    ) -> list[tuple[str, str]]:
        """Converts messages into a format understood by the ChatPromptTemplate - since it won't format
        BaseMessage derived classes for some reason, but will for tuples, because they get converted into
        Templates in function `_convert_to_message`."""
        return [(message.type, str(message.content)) for message in messages]

    @classmethod
    def escape_messages(
        cls,
        messages: Iterable[BaseMessage],
        allowed_keys: list[str],
    ) -> Iterable[BaseMessage]:
        """Adds escape curly braces to the messages, will make sure that the sequential
        curly braces in the messages is even (and hence escaped). Will ignore curly braces
        with `allowed_keys`."""

        def add_safeguards(content: str, char: str, allowed_keys: list[str]) -> str:
            start_idx: int = 0
            while True:
                char_idx: int = content.find(char, start_idx)
                if char_idx == -1:
                    break
                # Count how many sequences of the char are occuring
                count: int = 1
                # FIXME Add bounds check here
                while (
                    len(content) > char_idx + count
                    and content[char_idx + count] == char
                ):
                    count += 1

                # Check if the next sequence is in the allowed keys, if it is, then
                # skip to the next one.
                is_allowed: bool = False
                for key in allowed_keys:
                    if key == content[char_idx + count : char_idx + count + len(key)]:
                        is_allowed = True
                        break

                # Now change start_idx to reflect new location. The start index is at the end of
                # all the chars (including the inserted one).
                start_idx = char_idx + count + 1

                # If inside allowed keys, then continue to next iteration.
                if is_allowed:
                    continue

                # Check if odd number (will need to add extra char)
                if count % 2 != 0:
                    content = (
                        content[: char_idx + count] + char + content[char_idx + count :]
                    )
            return content

        reversed_keys: list[str] = [key[::-1] for key in allowed_keys]

        result: list[BaseMessage] = []
        for msg in messages:
            content: str = str(msg.content)
            look_pointer: int = 0
            # Open curly check
            if content.find("{", look_pointer) != -1:
                content = add_safeguards(content, "{", allowed_keys)
            # Close curly check
            if content.find("}", look_pointer) != -1:
                # Do it in reverse with reverse keys.
                content = add_safeguards(content[::-1], "}", reversed_keys)[::-1]
            new_msg = msg.copy()
            new_msg.content = content
            result.append(new_msg)
        return result

    def apply_chat_template(
        self,
        messages: Iterable[BaseMessage],
        **format_values: Any,
    ) -> PromptValue:
        """Applies the formatted values onto the message chat template. For example,
        if the message contains the token {source}, then format_values contains a
        value for {source} then it will be substituted."""
        escaped_messages = AIModel.escape_messages(messages, list(format_values.keys()))
        message_tuples = AIModel.convert_messages_to_tuples(escaped_messages)
        return ChatPromptTemplate.from_messages(messages=message_tuples).format_prompt(
            **format_values,
        )


class AIModelOpenAI(AIModel):
    context_length_exceeded_error: str = "context_length_exceeded"
    """Error code for when the length has been reached."""

    @override
    def create_llm(
        self,
        api_keys: APIKeyCollection,
        temperature: float = 1.0,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        assert api_keys.openai, "No OpenAI api key has been specified..."
        return ChatOpenAI(
            model=self.name,
            api_key=SecretStr(api_keys.openai),
            max_tokens=None,
            temperature=temperature,
            max_retries=requests_max_tries,
            timeout=requests_timeout,
            model_kwargs={},
        )

class OllamaAIModel(AIModel):
    def __init__(self, name: str, tokens: int, url: str) -> None:
        super().__init__(name, tokens)
        self.url: str = url
    
    @override
    def create_llm(self, api_keys: APIKeyCollection, temperature: float = 1, requests_max_tries: int = 5, requests_timeout: float = 60) -> BaseChatModel:
        # Ollama does not use API keys
        _ = api_keys
        _ = requests_max_tries
        return ChatOllama(
            base_url=self.url,
            model=self.name,
            temperature=temperature,
            client_kwargs={
                "timeout":requests_timeout,
            },
        )


class _AIModels(Enum):
    """Private enum that contains predefined AI Models. OpenAI models are not
    defined because they are fetched from the API."""

    # FALCON_7B = OllamaAIModel(...)
    pass


_custom_ai_models: list[AIModel] = []

_ai_model_names: set[str] = set(item.value.name for item in _AIModels)


def add_custom_ai_model(ai_model: AIModel) -> None:
    """Registers a custom AI model."""
    # Check if AI already already exists.
    if ai_model.name in _ai_model_names:
        raise Exception(f'AI Model "{ai_model.name}" already exists...')
    _ai_model_names.add(ai_model.name)
    _custom_ai_models.append(ai_model)


def is_valid_ai_model(
    ai_model: Union[str, AIModel], api_keys: Optional[APIKeyCollection] = None
) -> bool:
    """Accepts both the AIModel object and the name as parameter. It checks the
    openai servers to see if a model is defined on their servers, if not, then
    it checks the internally defined AI models list."""

    # Get the name of the model
    name: str = ai_model.name if isinstance(ai_model, AIModel) else ai_model

    # Try accessing openai api and checking if there is a model defined.
    # NOTE: This is not tested as no way to mock API currently.
    if api_keys and api_keys.openai:
        try:
            from openai import Client

            for model in Client(api_key=api_keys.openai).models.list().data:
                if model.id == name:
                    return True
        except ImportError:
            pass

    # Use the predefined list of models.
    return name in _ai_model_names


def _get_openai_model_max_tokens(name: str) -> int:
    """NOTE: OpenAI currently does not expose an API for getting the model
    length. Maybe add a config input value for this?"""

    # https://platform.openai.com/docs/models
    tokens = {
        "gpt-4o": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "gpt-3.5-turbo-instruct": 4096,
    }

    # Split into - segments and remove each section from the end to find out
    # which one matches the most.

    # Base Case
    if name in tokens:
        return tokens[name]

    # Step Case
    name_split: list[str] = name.split("-")
    for i in range(1, name.count("-")):
        subname: str = "-".join(name_split[:-i])
        if subname in tokens:
            return tokens[subname]

    raise ValueError(f"Could not figure out max tokens for model: {name}")


def get_ai_model_by_name(
    name: str, api_keys: Optional[APIKeyCollection] = None
) -> AIModel:
    # Check OpenAI models.
    if api_keys and api_keys.openai:
        try:
            from openai import Client

            for model in Client(api_key=api_keys.openai).models.list().data:
                if model.id == name:
                    add_custom_ai_model(
                        AIModelOpenAI(
                            model.id,
                            _get_openai_model_max_tokens(model.id),
                        ),
                    )
        except ImportError:
            pass

    # Check AIModels enum.
    for enum_value in _AIModels:
        ai_model: AIModel = enum_value.value
        if name == ai_model.name:
            return ai_model

    # Check custom AI models.
    for custom_ai in _custom_ai_models:
        if name == custom_ai.name:
            return custom_ai

    raise Exception(f'The AI "{name}" was not found...')
