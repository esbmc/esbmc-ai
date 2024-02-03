# Author: Yiannis Charalambous

import pytest

from langchain.llms.fake import FakeListLLM
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.base_chat_interface import BaseChatInterface
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings


@pytest.fixture
def setup():
    responses: list[str] = ["OK 1", "OK 2", "OK 3"]
    llm: FakeListLLM = FakeListLLM(responses=responses)

    ai_model: AIModel = AIModel("test", 1024)

    system_messages = [
        SystemMessage(content="System message"),
        AIMessage(content="OK"),
    ]

    chat: BaseChatInterface = BaseChatInterface(
        ai_model_agent=ChatPromptSettings(
            initial_prompt="",
            system_messages=AIAgentConversation.from_seq(system_messages),
            temperature=1.0,
        ),
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
        print(chat.ai_model_agent.system_messages.messages)
        print(chat.messages)


def test_send_message(regtest, setup) -> None:
    chat = setup

    chat_responses: list[ChatResponse] = [
        chat.send_message("Test 1"),
        chat.send_message("Test 2"),
        chat.send_message("Test 3"),
    ]

    with regtest:
        print(chat.ai_model_agent.system_messages.messages)
        print(chat.messages)
        print(chat_responses)
