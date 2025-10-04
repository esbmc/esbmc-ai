# Author: Yiannis Charalambous

from typing import Any
from uuid import UUID
from langchain.schema import BaseMessage, LLMResult
from typing_extensions import override
import structlog

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.callbacks import CallbackManager, BaseCallbackHandler


from esbmc_ai.config import Config
from esbmc_ai.log_utils import LogCategories


class LoggingCallbackHandler(BaseCallbackHandler):
    """Invoke callback handler is used to print debug messages to the LLM."""

    def __init__(self, ai_model: str) -> None:
        super().__init__()
        self.logger: structlog.stdlib.BoundLogger = structlog.get_logger().bind(
            category=LogCategories.CHAT,
            prefix_name=ai_model,
        )

    @override
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run when LLM starts running.

        .. ATTENTION::
            This method is called for non-chat models (regular LLMs). If you're
            implementing a handler for a chat model, you should use
            ``on_chat_model_start`` instead.

        Args:
            serialized (dict[str, Any]): The serialized LLM.
            prompts (list[str]): The prompts.
            run_id (UUID): The run ID. This is the ID of the current run.
            parent_run_id (UUID): The parent run ID. This is the ID of the parent run.
            tags (Optional[list[str]]): The tags.
            metadata (Optional[dict[str, Any]]): The metadata.
            kwargs (Any): Additional keyword arguments.
        """
        _ = run_id, parent_run_id, tags, metadata, kwargs
        self.logger.debug("Invoke LLM")

    @override
    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        _ = run_id, parent_run_id, kwargs
        self.logger.debug("LLM End")

    @override
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        _ = run_id, parent_run_id, kwargs
        self.logger.debug("LLM Error")

    @override
    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run when a chat model starts running.

        **ATTENTION**: This method is called for chat models. If you're implementing
        a handler for a non-chat model, you should use ``on_llm_start`` instead.

        Args:
            serialized (dict[str, Any]): The serialized chat model.
            messages (list[list[BaseMessage]]): The messages.
            run_id (UUID): The run ID. This is the ID of the current run.
            parent_run_id (UUID): The parent run ID. This is the ID of the parent run.
            tags (Optional[list[str]]): The tags.
            metadata (Optional[dict[str, Any]]): The metadata.
            kwargs (Any): Additional keyword arguments.
        """
        _ = run_id, parent_run_id, tags, metadata, kwargs
        self.logger.debug("Invoke Chat Model LLM")


class AIModel:
    """Loading utils for models."""

    @classmethod
    def get_model(
        cls,
        *,
        model: str,
        provider: str | None = None,
        temperature: float | None = None,
        url: str | None = None,
    ) -> BaseChatModel:
        chat_model: BaseChatModel = init_chat_model(
            model=model,
            model_provider=provider,
            temperature=temperature,
            max_tokens=None,  # Use all remaining tokens
            base_url=url,
            timeout=Config().llm_requests_timeout,
            max_retries=Config().llm_requests_max_retries,
            rate_limiter=InMemoryRateLimiter(
                requests_per_second=10,
                check_every_n_seconds=0.1,
                max_bucket_size=100,
            ),
        )

        handler: BaseCallbackHandler = LoggingCallbackHandler(
            ai_model=f"{provider}:{model}"
        )
        # Add the logging handler.
        if chat_model.callback_manager:
            chat_model.callback_manager.add_handler(handler)
        else:
            chat_model.callback_manager = CallbackManager([handler])

        return chat_model
