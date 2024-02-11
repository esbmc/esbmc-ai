# Author: Yiannis Charalambous

import pytest

from langchain.llms.fake import FakeListLLM
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from esbmc_ai.ai_models import AIModel
from esbmc_ai.base_chat_interface import BaseChatInterface
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings


@pytest.fixture(scope="module")
def setup():
    ai_model: AIModel = AIModel("test", 1024)

    system_messages: list[BaseMessage] = [
        SystemMessage(content="First system message"),
        AIMessage(content="OK"),
    ]

    return ai_model, system_messages


def test_push_message_stack(setup) -> None:
    llm: FakeListLLM = FakeListLLM(responses=[])

    ai_model, system_messages = setup

    chat: BaseChatInterface = BaseChatInterface(
        ai_model_agent=ChatPromptSettings(
            AIAgentConversation.from_seq(system_messages),
            initial_prompt="",
            temperature=1.0,
        ),
        ai_model=ai_model,
        llm=llm,
    )

    assert chat.ai_model_agent.system_messages.messages == tuple(system_messages)

    messages: list[BaseMessage] = [
        AIMessage(content="Test 1"),
        HumanMessage(content="Test 2"),
        SystemMessage(content="Test 3"),
    ]

    chat.push_to_message_stack(message=messages[0])
    chat.push_to_message_stack(message=messages[1])
    chat.push_to_message_stack(message=messages[2])

    assert chat.messages[0] == messages[0]
    assert chat.messages[1] == messages[1]
    assert chat.messages[2] == messages[2]


def test_send_message(setup) -> None:
    responses: list[str] = ["OK 1", "OK 2", "OK 3"]
    llm: FakeListLLM = FakeListLLM(responses=responses)

    ai_model, system_messages = setup

    chat: BaseChatInterface = BaseChatInterface(
        ai_model_agent=ChatPromptSettings(
            AIAgentConversation.from_seq(system_messages),
            initial_prompt="",
            temperature=1.0,
        ),
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
