# Author: Yiannis Charalambous

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import timedelta, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from platformdirs import user_cache_dir
from pydantic.types import SecretStr
from typing_extensions import override
import tiktoken
import structlog

from anthropic import Anthropic as AnthropicClient
from openai import Client as OpenAIClient

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import get_buffer_string
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain.prompts.chat import ChatPromptTemplate
from langchain.schema import (
    BaseMessage,
    HumanMessage,
    PromptValue,
)

from esbmc_ai.log_utils import LogCategories
from esbmc_ai.singleton import SingletonMeta


@dataclass(frozen=True, kw_only=True)
class AIModel(ABC):
    """This base class represents an abstract AI model. Each AIModel has the
    required properties to invoke the underlying langchain implementation
    BaseChatModel. To configure the properties, call the bind method and set
    them."""

    name: str
    tokens: int
    temperature: float = 1.0
    requests_max_tries: int = 5
    requests_timeout: float = 60
    _llm: BaseChatModel | None = field(default=None)

    def __post_init__(self):
        object.__setattr__(self, "_llm", self.create_llm())

    @abstractmethod
    def create_llm(self) -> BaseChatModel:
        """Initializes a langchain BaseChatModel with the provided parameters.
        Used internally by low-level functions. Bind should be used for
        AIModels."""
        raise NotImplementedError()

    def bind(self, **kwargs: Any) -> "AIModel":
        """Returns a new model with new parameters."""
        new_ai_model: AIModel = replace(self, **kwargs)
        llm: BaseChatModel = new_ai_model.create_llm()
        return replace(new_ai_model, _llm=llm)

    def invoke(self, input: LanguageModelInput, **kwargs: Any) -> BaseMessage:
        """Invokes the underlying BaseChatModel implementation and returns the
        message."""
        if not self._llm:
            raise ValueError("LLM is not initialized, call bind.")
        return self._llm.invoke(input, **kwargs)

    def get_num_tokens(self, content: str) -> int:
        """Gets the number of tokens for this AI model."""
        if not self._llm:
            raise ValueError("LLM is not initialized, call bind.")
        return self._llm.get_num_tokens(content)

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        """Gets the number of tokens for this AI model for a list of messages."""
        if not self._llm:
            raise ValueError("LLM is not initialized, call bind.")
        return self._llm.get_num_tokens_from_messages(messages)

    @classmethod
    def convert_messages_to_tuples(
        cls, messages: Iterable[BaseMessage]
    ) -> list[tuple[str, str]]:
        """Converts messages into a format understood by the ChatPromptTemplate,
        since it won't format BaseMessage derived classes for some reason, but
        will for tuples, because they get converted into Templates in function
        `_convert_to_message`."""
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
            new_msg = msg.model_copy()
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

    def apply_str_template(
        self,
        text: str,
        **format_values: Any,
    ) -> str:
        """Applies the formatted values onto a string template. For example,
        if the message contains the token {source}, then format_values contains a
        value for {source} then it will be substituted."""

        prompt: HumanMessage = HumanMessage(content=text)
        result: str = str(
            self.apply_chat_template(messages=[prompt], **format_values)
            .to_messages()[0]
            .content
        )

        return result


@dataclass(frozen=True, kw_only=True)
class AIModelService(AIModel):
    """Represents an AI model from a service."""

    api_key: str = ""

    @staticmethod
    def _get_max_tokens(name: str, token_groups: dict[str, int]) -> int:
        """Dynamically resolves the max tokens from a base model."""

        # Split into - segments and remove each section from the end to find out
        # which one matches the most.

        # Base Case
        if name in token_groups:
            return token_groups[name]

        # Step Case
        name_split: list[str] = name.split("-")
        for i in range(1, name.count("-")):
            subname: str = "-".join(name_split[:-i])
            if subname in token_groups:
                return token_groups[subname]

        raise ValueError(f"Could not figure out max tokens for model: {name}")

    @classmethod
    @abstractmethod
    def get_models_list(cls, api_key: str) -> list[str]:
        """Get available models from the API service."""
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def create_model(cls, name: str) -> "AIModel":
        """Create an AI model instance from model name."""
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_cache_filename(cls) -> str:
        """Get the cache filename for this service."""
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_canonical_name(cls) -> str:
        """Get the canonical name of this service for dictionary access (lowercase)."""
        raise NotImplementedError()


@dataclass(frozen=True, kw_only=True)
class AIModelOpenAI(AIModelService):
    """OpenAI model."""

    requests_max_tries: int = 5
    requests_timeout: float = 60

    @property
    def _reason_model(self) -> bool:
        if "o3-mini" in self.name:
            return True
        return False

    @override
    def create_llm(self) -> BaseChatModel:
        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = (SecretStr(self.api_key) or None,)
        return ChatOpenAI(
            model=self.name,
            temperature=None if self._reason_model else self.temperature,
            reasoning_effort="high" if self._reason_model else None,
            max_retries=self.requests_max_tries,
            timeout=self.requests_timeout,
            model_kwargs={},
            **kwargs,
        )

    @override
    def get_num_tokens(self, content: str) -> int:
        encoding: tiktoken.Encoding = tiktoken.encoding_for_model(self.name)
        return len(encoding.encode(content))

    @override
    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        encoding: tiktoken.Encoding = tiktoken.encoding_for_model(self.name)
        return sum(len(encoding.encode(get_buffer_string([m]))) for m in messages)

    @classmethod
    def get_max_tokens(cls, name: str) -> int:
        """Dynamically resolves the max tokens from a base model."""
        # https://platform.openai.com/docs/models
        tokens: dict[str, int] = {
            "gpt-3.5": 16385,
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4.1": 1047576,
            "gpt-4.5": 128000,
            "gpt-4o": 128000,
            "o1": 200000,
            "o3": 200000,
            "o4-mini": 200000,
        }
        return cls._get_max_tokens(name, tokens)

    @classmethod
    def get_models_list(cls, api_key: str) -> list[str]:
        """Get available models from the OpenAI API service."""
        if not api_key:
            return []
        try:
            return [
                str(model.id)
                for model in OpenAIClient(api_key=api_key).models.list().data
            ]
        except ImportError:
            return []

    @classmethod
    def create_model(cls, name: str) -> "AIModel":
        """Create an OpenAI AI model instance from model name."""
        return cls(
            name=name.strip(),
            tokens=cls.get_max_tokens(name),
        )

    @classmethod
    def get_cache_filename(cls) -> str:
        """Get the cache filename for OpenAI service."""
        return "openai_models.txt"

    @classmethod
    def get_canonical_name(cls) -> str:
        """Get the canonical name of the OpenAI service."""
        return "openai"


@dataclass(frozen=True, kw_only=True)
class OllamaAIModel(AIModel):
    """A model that is running on the Ollama service."""

    url: str

    @override
    def create_llm(self) -> BaseChatModel:
        return ChatOllama(
            base_url=self.url,
            model=self.name,
            temperature=self.temperature,
            client_kwargs={
                "timeout": self.requests_timeout,
            },
        )


class AIModelAnthropic(AIModelService):
    """An AI model that uses the Anthropic service."""

    @override
    def create_llm(self) -> BaseChatModel:
        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = SecretStr(self.api_key) or None
        return ChatAnthropic(  # pyright: ignore [reportCallIssue]
            model_name=self.name,
            temperature=self.temperature,
            timeout=self.requests_timeout,
            max_retries=self.requests_max_tries,
            **kwargs,
        )

    @classmethod
    def get_max_tokens(cls, name: str) -> int:
        # docs.anthropic.com/en/docs/about-claude/models/overview#model-names
        tokens = {
            "claude-3": 200000,
            "claude-sonnet-4": 200000,
            "claude-opus-4": 200000,
        }

        return cls._get_max_tokens(name, tokens)

    @override
    def get_num_tokens(self, content: str) -> int:
        # Delete trailing whitespace from last message because of (this might
        # change in the future because of their API):
        # anthropic.BadRequestError: Error code: 400
        # final assistant content cannot end with trailing whitespace.
        return super().get_num_tokens(content.strip())

    @override
    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        # Delete trailing whitespace from last message because of (this might
        # change in the future because of their API):
        # anthropic.BadRequestError: Error code: 400
        # final assistant content cannot end with trailing whitespace.
        if messages:
            messages[-1].content = str(messages[-1].content).strip()
        return super().get_num_tokens_from_messages(messages)

    @classmethod
    def get_models_list(cls, api_key: str) -> list[str]:
        """Get available models from the Anthropic API service."""
        if not api_key:
            return []
        client = AnthropicClient(api_key=api_key)
        return [str(i.id) for i in client.models.list()] + [
            # Include also latest models ID not returned by the API but can be
            # used to use the latest version of a model.
            # docs.anthropic.com/en/docs/about-claude/models/overview#model-aliases
            "claude-opus-4-0",
            "claude-sonnet-4-0",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ]

    @classmethod
    def create_model(cls, name: str) -> "AIModel":
        """Create an Anthropic AI model instance from model name."""
        return cls(
            name=name.strip(),
            tokens=cls.get_max_tokens(name),
        )

    @classmethod
    def get_cache_filename(cls) -> str:
        """Get the cache filename for Anthropic service."""
        return "anthropic_models.txt"

    @classmethod
    def get_canonical_name(cls) -> str:
        """Get the canonical name of the Anthropic service."""
        return "anthropic"


class AIModels(metaclass=SingletonMeta):
    """Manages the loading of AI Models from different sources."""

    def __init__(self) -> None:
        super().__init__()

        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger().bind(
            category=LogCategories.SYSTEM,
        )
        self._api_keys: dict[str, str] = {}
        self._ai_models: dict[str, AIModel] = {}
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load_default_models(
        self,
        api_keys: dict[str, str],
        refresh_duration_seconds: int = 86400,
    ) -> None:
        """Loads the default AI models from OpenAI and Anthropic services.

        Args:
            api_keys - Dictionary with the canonical names of the models as keys
                for API access. If a model does not come with a valid API key,
                then it will not load the models.
            refresh_duration_seconds - If the refresh duration has passed since
                the last update, then the models will be loaded from the API
                rather from cache."""

        self._api_keys = api_keys

        # Load models from each service
        services = [AIModelOpenAI, AIModelAnthropic]
        for service in services:
            api_key = api_keys.get(service.get_canonical_name(), "")
            self._load_service_ai_models_list(
                service=service,
                api_key=api_key,
                refresh_duration_seconds=refresh_duration_seconds,
            )

    @property
    def model_names(self) -> list[str]:
        return list(self._ai_models.keys())

    @property
    def _cache_dir(self) -> Path:
        cache: Path = Path(user_cache_dir("esbmc-ai", "Yiannis Charalambous"))
        return cache

    def is_valid_ai_model(self, ai_model: str | AIModel) -> bool:
        """Returns true if the model exists."""

        # Get the name of the model
        name: str = ai_model.name if isinstance(ai_model, AIModel) else ai_model

        # Use the predefined list of models.
        return name in self._ai_models

    @property
    def ai_models(self) -> dict[str, AIModel]:
        """Gets all loaded AI models"""
        return self._ai_models

    def get_ai_model(self, name: str) -> AIModel:
        """Checks for built-in and custom_ai models"""
        if name in self._ai_models:
            return self._ai_models[name]

        raise KeyError(f'The AI "{name}" was not found...')

    def add_ai_model(self, ai_model: AIModel, replace: bool = False) -> None:
        """Registers a custom AI model."""
        # Check if AI already already exists.
        if ai_model.name in self._ai_models and not replace:
            raise KeyError(f'AI Model "{ai_model.name}" already exists...')

        self._ai_models[ai_model.name] = ai_model

    def _load_service_ai_models_list(
        self,
        service: type[AIModelService],
        api_key: str,
        refresh_duration_seconds: int,
    ) -> None:
        """Loads the service model names from cache or refreshes them from the internet."""

        duration = timedelta(seconds=refresh_duration_seconds)
        service_name = service.get_canonical_name().title()
        cache_name = service.get_cache_filename()
        self._logger.info(f"Loading {service_name} models list")
        models_list: list[str] = []

        # Read the last updated date to determine if a new update is required
        try:
            last_update, models_list = self._load_cache(cache_name)
            # Write new & updated cache file
            if datetime.now() >= last_update + duration:
                self._logger.info("\tModels list outdated, refreshing...")
                models_list = service.get_models_list(api_key)
                self._write_cache(cache_name, models_list)
        except ValueError as e:
            self._logger.error(f"Loading {service_name} models list failed:", e)
            self._logger.info("\tCreating new models list.")
            models_list = service.get_models_list(api_key)
            self._write_cache(cache_name, models_list)
        except FileNotFoundError:
            self._logger.info("\tModels list not found, creating new...")
            models_list = service.get_models_list(api_key)
            self._write_cache(cache_name, models_list)

        # Add models that have been loaded.
        for model_name in models_list:
            try:
                self.add_ai_model(service.create_model(model_name), replace=True)
            except ValueError as e:
                # Ignore models that don't count, like image only models.
                self._logger.debug(f"Could not add model: {e}")
                pass

    def _write_cache(self, name: str, models_list: list[str]):
        with open(self._cache_dir / name, "w") as file:
            file.seek(0)
            file.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            file.writelines(model_name + "\n" for model_name in models_list)
        return models_list

    def _load_cache(self, path: str) -> tuple[datetime, list[str]]:
        cache: Path = Path(user_cache_dir("esbmc-ai", "Yiannis Charalambous"))
        cache.mkdir(parents=True, exist_ok=True)
        with open(self._cache_dir / path, "r") as file:
            last_update: datetime = datetime.strptime(
                file.readline().strip(), "%Y-%m-%d %H:%M:%S"
            )
            return last_update, file.readlines()
