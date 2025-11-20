# Author: Yiannis Charalambous

"""Template renderer that integrates TemplateKeyProvider with ChatPromptTemplate."""

from typing import Any, Sequence, override
from jinja2.sandbox import SandboxedEnvironment
from langchain_core.messages import BaseMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import MessageLikeRepresentation
from langchain_core.prompts.string import PromptTemplateFormat, DEFAULT_FORMATTER_MAPPING
from pydantic import PrivateAttr, BaseModel
from esbmc_ai.chats.template_key_provider import TemplateKeyProvider
from .template_funcs import get_func_mapping


class _PermissiveSandboxedEnvironment(SandboxedEnvironment):
    """Custom Jinja2 sandbox that allows attribute access on trusted objects.

    This environment allows attribute access on Pydantic models and other
    trusted objects while still providing basic sandboxing protections.
    """

    def is_safe_attribute(self, obj: Any, attr: str, value: Any) -> bool:
        """Allow attribute access on Pydantic models and common types."""
        # Allow attribute access on Pydantic models
        if isinstance(obj, BaseModel):
            return True
        # Allow attribute access on dicts, lists, and other safe types
        if isinstance(obj, (dict, list, tuple, str, int, float, bool, type(None))):
            return True
        # Default to parent's behavior for other types
        return super().is_safe_attribute(obj, attr, value)


def _permissive_jinja2_formatter(template: str, **kwargs: Any) -> str:
    """Format a template using a permissive Jinja2 sandbox.

    Unlike LangChain's default restricted sandbox, this allows attribute
    access on trusted objects like Pydantic models.
    """
    env = _PermissiveSandboxedEnvironment()
    return env.from_string(template).render(**kwargs)


# Override LangChain's default jinja2 formatter with our permissive one
# This allows nested attribute access on Pydantic models in templates
DEFAULT_FORMATTER_MAPPING["jinja2"] = _permissive_jinja2_formatter


class KeyTemplateRenderer(ChatPromptTemplate):
    """Derives ChatPromptTemplate and automatically provides template keys via
    TemplateKeyProvider. This is to force standarization across types and keys."""

    _key_provider: TemplateKeyProvider = PrivateAttr()

    def __init__(
        self,
        messages: Sequence[MessageLikeRepresentation],
        key_provider: TemplateKeyProvider,
        *,
        template_format: PromptTemplateFormat = "jinja2",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            template_format=template_format,
            **kwargs,
        )
        self._key_provider = key_provider

    @override
    def format_prompt(self, **kwargs: Any) -> ChatPromptValue:
        auto_keys = self._key_provider.get_template_keys(**kwargs)
        kwargs = {**auto_keys, **kwargs} | get_func_mapping()
        return super().format_prompt(**kwargs)

    @override
    def format_messages(self, **kwargs: Any) -> list[BaseMessage]:
        auto_keys = self._key_provider.get_template_keys(**kwargs)
        kwargs = {**auto_keys, **kwargs} | get_func_mapping()
        return super().format_messages(**kwargs)

    @override
    def format(self, **kwargs: Any) -> str:
        auto_keys = self._key_provider.get_template_keys(**kwargs)
        kwargs = {**auto_keys, **kwargs} | get_func_mapping()
        return super().format(**kwargs)
