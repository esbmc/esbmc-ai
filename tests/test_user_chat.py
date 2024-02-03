# Author: Yiannis Charalambous

import pytest

from langchain.llms.fake import FakeListLLM
from langchain.schema import AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings
from esbmc_ai.user_chat import UserChat


@pytest.fixture
def setup():
    system_messages: list = [
        SystemMessage(content="This is a system message"),
        AIMessage(content="OK"),
    ]

    set_solution_messages = [
        SystemMessage(content="Corrected output"),
    ]

    summary_text = "THIS IS A SUMMARY OF THE CONVERSATION"
    chat: UserChat = UserChat(
        ai_model_agent=ChatPromptSettings(
            system_messages=AIAgentConversation.from_seq(system_messages),
            initial_prompt="This is initial prompt",
            temperature=1.0,
        ),
        ai_model=AIModel(name="test", tokens=12),
        llm=FakeListLLM(responses=[summary_text]),
        source_code="This is source code",
        esbmc_output="This is esbmc output",
        set_solution_messages=AIAgentConversation.from_seq(set_solution_messages),
    )

    return chat, summary_text, system_messages


def test_compress_message_stack(setup) -> None:
    chat, summary_text, system_messages = setup

    chat.messages = [SystemMessage(content=chat.ai_model_agent.initial_prompt)]

    chat.compress_message_stack()

    # Check system messages
    assert chat.ai_model_agent.system_messages.messages == tuple(system_messages)

    # Check normal messages
    assert chat.messages == [SystemMessage(content=summary_text)]


def test_automatic_compress(setup) -> None:
    chat, summary_text, system_messages = setup

    # Make the prompt extra large.
    big_prompt: str = chat.ai_model_agent.initial_prompt * 10

    response: ChatResponse = chat.send_message(big_prompt)

    assert response.finish_reason == FinishReason.length

    chat.compress_message_stack()

    # Check system messages
    assert chat.ai_model_agent.system_messages.messages == tuple(system_messages)

    # Check normal messages - Should be summarized automatically
    assert chat.messages == [SystemMessage(content=summary_text)]
