"""ESBMC-AI is an AI augmentation layer over ESBMC, the Efficient
Software Bounded Model Checker. With the power of LLMs, it adds
features such as automatic code fixing and more."""

from esbmc_ai.__about__ import __version__, __author__

from esbmc_ai.config import Config
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.base_component import BaseComponent, BaseComponentConfig
from esbmc_ai.verifiers import BaseSourceVerifier
from esbmc_ai.ai_models import AIModel
from esbmc_ai.log_categories import LogCategories
from esbmc_ai.chats.key_template_renderer import KeyTemplateRenderer
from esbmc_ai.chats.template_key_provider import (
    TemplateKeyProvider,
    GenericTemplateKeyProvider,
    OracleTemplateKeyProvider,
)

__all__ = [
    "Config",
    "BaseComponent",
    "BaseComponentConfig",
    "ChatCommand",
    "BaseSourceVerifier",
    "AIModel",
    "LogCategories",
    "KeyTemplateRenderer",
    "TemplateKeyProvider",
    "GenericTemplateKeyProvider",
    "OracleTemplateKeyProvider",
]
