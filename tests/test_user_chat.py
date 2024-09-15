# Author: Yiannis Charalambous

from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.chats.user_chat import UserChat


@pytest.fixture
def setup():
    system_messages: list = [
        SystemMessage(content="This is a system message"),
        AIMessage(content="OK"),
    ]

    summary_text = "THIS IS A SUMMARY OF THE CONVERSATION"
    chat: UserChat = UserChat(
        system_messages=system_messages,
        ai_model=AIModel(name="test", tokens=12),
        llm=FakeListChatModel(responses=[summary_text]),
        source_code="This is source code",
        esbmc_output="This is esbmc output",
        set_solution_messages=[
            SystemMessage(content="Corrected output"),
        ],
    )

    return chat, summary_text, system_messages


@pytest.fixture
def initial_prompt():
    return "This is initial prompt"


def test_compress_message_stack(setup, initial_prompt) -> None:
    chat, summary_text, system_messages = setup

    chat.messages = [SystemMessage(content=initial_prompt)]

    chat.compress_message_stack()

    # Check system messages
    for msg, chat_msg in zip(system_messages, chat._system_messages):
        assert msg.type == chat_msg.type and msg.content == chat_msg.content

    # Check normal messages
    assert chat.messages[0].content == summary_text


def test_automatic_compress(setup, initial_prompt) -> None:
    chat, summary_text, system_messages = setup

    # Make the prompt extra large.
    big_prompt: str = initial_prompt * 10

    response: ChatResponse = chat.send_message(big_prompt)

    assert response.finish_reason == FinishReason.length

    chat.compress_message_stack()

    # Check system messages
    for msg, chat_msg in zip(system_messages, chat._system_messages):
        assert msg.type == chat_msg.type and msg.content == chat_msg.content

    # Check normal messages - Should be summarized automatically
    assert chat.messages[0].content == summary_text
