# Author: Yiannis Charalambous

"""Template renderer that integrates TemplateKeyProvider with ChatPromptTemplate."""

from typing import Any, Sequence, override
from langchain_core.messages import BaseMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import MessageLikeRepresentation
from langchain_core.prompts.string import PromptTemplateFormat
from pydantic import PrivateAttr
from esbmc_ai.chats.template_key_provider import TemplateKeyProvider
from .template_funcs import get_func_mapping


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
