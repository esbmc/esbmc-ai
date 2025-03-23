# Author: Yiannis Charalambous

from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from esbmc_ai.chats.base_chat_interface import BaseChatInterface
from esbmc_ai.chat_response import ChatResponse
from tests.test_ai_models import MockAIModel


@pytest.fixture(scope="module")
def setup():
    ai_model: MockAIModel = MockAIModel("test", 1024)

    system_messages: list[BaseMessage] = [
        SystemMessage(content="First system message"),
        AIMessage(content="OK"),
    ]

    return ai_model, system_messages


def test_push_message_stack(setup) -> None:
    llm: FakeListChatModel = FakeListChatModel(responses=[])

    ai_model, system_messages = setup

    chat: BaseChatInterface = BaseChatInterface(
        system_messages=system_messages,
        ai_model=ai_model,
        llm=llm,
    )

    for msg, chat_msg in zip(system_messages, chat._system_messages):
        assert msg.type == chat_msg.type
        assert msg.content == chat_msg.content

    messages: list[BaseMessage] = [
        AIMessage(content="Test 1"),
        HumanMessage(content="Test 2"),
        SystemMessage(content="Test 3"),
        SystemMessage(content="Test 4"),
        SystemMessage(content="Test 5"),
        SystemMessage(content="Test 6"),
    ]

    chat.push_to_message_stack(message=messages[0])
    chat.push_to_message_stack(message=messages[1])
    chat.push_to_message_stack(message=messages[2])

    assert chat.messages[0] == messages[0]
    assert chat.messages[1] == messages[1]
    assert chat.messages[2] == messages[2]

    chat.push_to_message_stack(message=messages[3:])

    assert chat.messages[3] == messages[3]
    assert chat.messages[4] == messages[4]
    assert chat.messages[5] == messages[5]


def test_send_message(setup) -> None:
    responses: list[str] = ["OK 1", "OK 2", "OK 3"]
    llm: FakeListChatModel = FakeListChatModel(responses=responses)

    ai_model, system_messages = setup

    chat: BaseChatInterface = BaseChatInterface(
        system_messages=system_messages,
        ai_model=ai_model,
        llm=llm,
    )

    chat_responses: list[ChatResponse] = [
        chat.send_message("Test 1"),
        chat.send_message("Test 2"),
        chat.send_message("Test 3"),
    ]

    assert chat_responses[0].message.content == responses[0]
    assert chat_responses[1].message.content == responses[1]
    assert chat_responses[2].message.content == responses[2]


def test_apply_template() -> None:
    ai_model: MockAIModel = MockAIModel("test", 1024)

    system_messages: list[BaseMessage] = [
        SystemMessage(content="This is a {source_code} message"),
        SystemMessage(content="Replace with {esbmc_output} message"),
        SystemMessage(content="{source_code}{esbmc_output}"),
    ]

    responses: list[str] = [
        "This is a replaced message",
        "Replace with {esbmc_output} message",
        "replaced{esbmc_output}",
        "This is a replaced message",
        "Replace with also replaced message",
        "replacedalso replaced",
    ]
    llm: FakeListChatModel = FakeListChatModel(responses=responses)

    chat: BaseChatInterface = BaseChatInterface(
        system_messages=system_messages,
        ai_model=ai_model,
        llm=llm,
    )

    chat.apply_template_value(source_code="replaced")

    assert chat._system_messages[0].content == responses[0]
    assert chat._system_messages[1].content == responses[1]
    assert chat._system_messages[2].content == responses[2]

    chat.apply_template_value(esbmc_output="also replaced")

    assert chat._system_messages[0].content == responses[3]
    assert chat._system_messages[1].content == responses[4]
    assert chat._system_messages[2].content == responses[5]
