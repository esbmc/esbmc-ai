# Author: Yiannis Charalambous

from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.chats.base_chat_interface import BaseChatInterface


@pytest.fixture
def setup():
    responses: list[str] = ["OK 1", "OK 2", "OK 3"]
    llm: FakeListChatModel = FakeListChatModel(responses=responses)

    ai_model: AIModel = AIModel("test", 1024)

    system_messages = [
        SystemMessage(content="System message"),
        AIMessage(content="OK"),
    ]

    chat: BaseChatInterface = BaseChatInterface(
        system_messages=system_messages,
        ai_model=ai_model,
        llm=llm,
    )

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
    chat = setup

    chat_responses: list[ChatResponse] = [
        chat.send_message("Test 1"),
        chat.send_message("Test 2"),
        chat.send_message("Test 3"),
    ]

    with regtest:
        print("System Messages:")
        for m in chat._system_messages:
            print(f"{m.type}: {m.content}")
        print("Chat Messages:")
        for m in chat.messages:
            print(f"{m.type}: {m.content}")
        print("Responses:")
        for m in chat_responses:
            print(
                f"{m.message.type}({m.total_tokens} - {m.finish_reason}): {m.message.content}"
            )
