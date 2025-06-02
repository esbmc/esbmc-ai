# Author: Yiannis Charalambous

import pytest

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.chats.base_chat_interface import BaseChatInterface
from tests.test_ai_models import MockAIModel
from pprint import pprint


@pytest.fixture
def setup() -> BaseChatInterface:
    responses: list[str] = ["OK 1", "OK 2", "OK 3"]

    ai_model: AIModel = MockAIModel(name="test", tokens=1024, responses=responses)
    ai_model: AIModel = MockAIModel(
        name="test", tokens=1024, responses=responses
    ).bind()
    assert isinstance(ai_model, MockAIModel)

    system_messages = [
        SystemMessage(content="System message"),
        AIMessage(content="OK"),
    ]

    chat: BaseChatInterface = BaseChatInterface(
        system_messages=system_messages,
        ai_model=ai_model,
    )
    chat.cooldown_total = 0

    return chat


def test_push_message_stack(regtest, setup) -> None:
    chat = setup

    messages: list[BaseMessage] = [
        AIMessage(content="Test 1"),
        HumanMessage(content="Test 2"),
        SystemMessage(content="Test 3"),
    ]

    chat.push_to_message_stack(messages[0])
    chat.push_to_message_stack(messages[1])
    chat.push_to_message_stack(messages[2])

    with regtest:
        for msg in chat._system_messages:
            print(f"{msg.type}: {msg.content}")

        for msg in chat.messages:
            print(f"{msg.type}: {msg.content}")


def test_send_message(regtest, setup) -> None:
    chat: BaseChatInterface = setup

    with regtest:
        r: ChatResponse = chat.send_message("Test 1")
        print(r.finish_reason, r.total_tokens, r.message.content)
        r = chat.send_message("Test 2")
        print(r.finish_reason, r.total_tokens, r.message.content)
        r = chat.send_message("Test 3")
        print(r.finish_reason, r.total_tokens, r.message.content)
        # Show system messages
        for idx, msg in enumerate(chat._system_messages):
            print("System message:", idx, msg.content)
        for idx, msg in enumerate(chat.messages):
            print("Message:", idx, msg.content)
