# Author: Yiannis Charalambous

from abc import abstractmethod
from datetime import timedelta, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from platformdirs import user_cache_dir
from typing_extensions import override
import tiktoken
import structlog

from anthropic import Anthropic as AnthropicClient
from openai import Client as OpenAIClient

from langchain_core.language_models import BaseChatModel
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


class AIModel:
    """This base class represents an abstract AI model."""

    def __init__(
        self,
        name: str,
        tokens: int,
    ) -> None:
        self.name: str = name
        self.tokens: int = tokens

    @abstractmethod
    def create_llm(
        self,
        temperature: float = 1.0,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        """Initializes a large language model model with the provided parameters."""
        raise NotImplementedError()

    def get_num_tokens(self, content: str) -> int:
        """Gets the number of tokens for this AI model."""
        return self.create_llm().get_num_tokens(content)

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        """Gets the number of tokens for this AI model for a list of messages."""
        return self.create_llm().get_num_tokens_from_messages(messages)

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


class AIModelService(AIModel):
    """Represents an AI model from a service."""

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


class AIModelOpenAI(AIModelService):
    """OpenAI model."""

    context_length_exceeded_error: str = "context_length_exceeded"
    """Error code for when the length has been reached."""

    @property
    def _reason_model(self) -> bool:
        if "o3-mini" in self.name:
            return True
        return False

    @override
    def create_llm(
        self,
        temperature: float = 1.0,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        return ChatOpenAI(
            model=self.name,
            temperature=None if self._reason_model else temperature,
            reasoning_effort="high" if self._reason_model else None,
            max_retries=requests_max_tries,
            timeout=requests_timeout,
            model_kwargs={},
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


class OllamaAIModel(AIModel):
    """A model that is running on the Ollama service."""

    def __init__(self, name: str, tokens: int, url: str) -> None:
        super().__init__(name, tokens)
        self.url: str = url

    @override
    def create_llm(
        self,
        temperature: float = 1,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        # Ollama does not use API keys
        _ = requests_max_tries
        return ChatOllama(
            base_url=self.url,
            model=self.name,
            temperature=temperature,
            client_kwargs={
                "timeout": requests_timeout,
            },
        )


class AIModelAnthropic(AIModelService):
    """An AI model that uses the Anthropic service."""

    @override
    def create_llm(
        self,
        temperature: float = 1,
        requests_max_tries: int = 5,
        requests_timeout: float = 60,
    ) -> BaseChatModel:
        return ChatAnthropic(  # pyright: ignore [reportCallIssue]
            model_name=self.name,
            temperature=temperature,
            timeout=requests_timeout,
            max_retries=requests_max_tries,
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

    def load_models(
        self, api_keys: dict[str, str], refresh_duration_seconds: int = 86400
    ) -> None:
        """Loads the AI models."""

        self._api_keys = api_keys

        self._load_ai_model_list(
            source_name="OpenAI",
            cache_name="openai_models.txt",
            refresh_duration_seconds=refresh_duration_seconds,
            get_models_list=self._get_openai_models_list,
            new_ai_model=lambda v: AIModelOpenAI(
                v.strip(),
                AIModelOpenAI.get_max_tokens(v),
            ),
        )
        self._load_ai_model_list(
            source_name="Anthropic",
            cache_name="anthropic_models.txt",
            refresh_duration_seconds=refresh_duration_seconds,
            get_models_list=self._get_anthropic_models_list,
            new_ai_model=lambda v: AIModelAnthropic(
                v.strip(),
                AIModelAnthropic.get_max_tokens(v),
            ),
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

    def add_ai_model(self, ai_model: AIModel) -> None:
        """Registers a custom AI model."""
        # Check if AI already already exists.
        if ai_model.name in self._ai_models:
            raise KeyError(f'AI Model "{ai_model.name}" already exists...')
        self._ai_models[ai_model.name] = ai_model

    def _load_ai_model_list(
        self,
        source_name: str,
        cache_name: str,
        refresh_duration_seconds: int,
        get_models_list: Callable[[], list[str]],
        new_ai_model: Callable[[str], AIModel],
    ) -> None:
        """Loads the service model names from cache or refreshes them from the internet."""

        duration = timedelta(seconds=refresh_duration_seconds)
        self._logger.info(f"Loading {source_name} models list")
        models_list: list[str] = []

        # Read the last updated date to determine if a new update is required
        try:
            last_update, models_list = self._load_cache(cache_name)
            # Write new & updated cache file
            if datetime.now() >= last_update + duration:
                self._logger.info("\tModels list outdated, refreshing...")
                models_list = get_models_list()
                self._write_cache(cache_name, models_list)
        except ValueError as e:
            self._logger.error(f"Loading {source_name} models list failed:", e)
            self._logger.info("\tCreating new models list.")
            models_list = get_models_list()
            self._write_cache(cache_name, models_list)
        except FileNotFoundError:
            self._logger.info("\tModels list not found, creating new...")
            models_list = get_models_list()
            self._write_cache(cache_name, models_list)

        # Add models that have been loaded.
        for model_name in models_list:
            try:
                self.add_ai_model(new_ai_model(model_name))
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

    def _get_openai_models_list(self) -> list[str]:
        """Gets the open AI models from the API service and returns them."""

        if "openai" not in self._api_keys:
            return []

        try:
            return [str(model.id) for model in OpenAIClient().models.list().data]
        except ImportError:
            return []

    def _get_anthropic_models_list(self) -> list[str]:
        if "anthropic" not in self._api_keys:
            return []
        client = AnthropicClient(api_key=self._api_keys["anthropic"])
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
