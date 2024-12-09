# Author: Yiannis Charalambous

from enum import Enum
from typing import NamedTuple

from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)


"""Contains classes and functions that relate to sending/receiving messages from LLMs."""


class FinishReason(Enum):
    # API response still in progress or incomplete
    null = 0
    # API returned complete model output
    stop = 1
    # Incomplete model output due to max_tokens parameter or token limit
    length = 2
    # Omitted content due to a flag from our content filters
    content_filter = 3


class ChatResponse(NamedTuple):
    message: BaseMessage = AIMessage(content="")
    total_tokens: int = 0
    finish_reason: FinishReason = FinishReason.null


def dict_to_base_message(json_string: dict) -> BaseMessage:
    """Converts a json representation of messages (such as in config.json),
    into LangChain object messages. The three recognized roles are:
    1. System
    2. AI
    3. Human"""
    role: str = json_string["role"]
    content: str = json_string["content"]
    if role == "System":
        return SystemMessage(content=content)
    elif role == "AI":
        return AIMessage(content=content)
    elif role == "Human":
        return HumanMessage(content=content)
    else:
        raise Exception()


def list_to_base_messages(json_messages: list[dict]) -> tuple[BaseMessage, ...]:
    """Converts a list of messages from JSON format to a list of BaseMessage."""
    return tuple(dict_to_base_message(msg) for msg in json_messages)
