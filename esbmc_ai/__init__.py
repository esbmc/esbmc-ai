"""ESBMC-AI is an AI augmentation layer over ESBMC, the Efficient
Software Bounded Model Checker. With the power of LLMs, it adds
features such as automatic code fixing and more."""

from esbmc_ai.__about__ import __version__, __author__

from esbmc_ai.config import Config
from esbmc_ai.chat_command import ChatCommand

__all__ = ["Config", "ChatCommand"]
