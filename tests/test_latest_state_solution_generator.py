# Author: Yiannis Charalambous

from typing import Optional
from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import HumanMessage, AIMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings
from esbmc_ai.chats.latest_state_solution_generator import LatestStateSolutionGenerator


@pytest.fixture(scope="function")
def setup_llm_model():
    llm = FakeListChatModel(
        responses=[
            "This is a test response",
            "Another test response",
            "One more!",
        ],
    )
    model = AIModel("test model", 1000)
    return llm, model


def test_send_message(setup_llm_model) -> None:
    llm, model = setup_llm_model
    chat_settings = ChatPromptSettings(
        system_messages=AIAgentConversation(
            messages=(
                SystemMessage(content="Test message 1"),
                HumanMessage(content="Test message 2"),
                AIMessage(content="Test message 3"),
            ),
        ),
        initial_prompt="Initial test message",
        temperature=1.0,
    )

    solution_generator = LatestStateSolutionGenerator(
        llm=llm,
        ai_model=model,
        ai_model_agent=chat_settings,
    )

    def send_message_mock(message: Optional[str] = None) -> ChatResponse:
        assert len(solution_generator.messages) == 1
        assert solution_generator.messages[0] == HumanMessage(
            content=chat_settings.initial_prompt,
        )

        return ChatResponse()

    # Use the LLM method to check if the code is overwritten
    solution_generator.send_message = send_message_mock

    solution_generator.update_state("", "")

    solution_generator.generate_solution()
    chat_settings.initial_prompt = "aaaaaaa"
    solution_generator.generate_solution()
    chat_settings.initial_prompt = "bbbbbbb"
    solution_generator.generate_solution()
    chat_settings.initial_prompt = "ccccccc"


def test_message_stack(setup_llm_model) -> None:
    llm, model = setup_llm_model

    chat_settings = ChatPromptSettings(
        system_messages=AIAgentConversation(
            messages=(
                SystemMessage(content="Test message 1"),
                HumanMessage(content="Test message 2"),
                AIMessage(content="Test message 3"),
            ),
        ),
        initial_prompt="Initial test message",
        temperature=1.0,
    )

    solution_generator = LatestStateSolutionGenerator(
        llm=llm,
        ai_model=model,
        ai_model_agent=chat_settings,
    )

    with pytest.raises(AssertionError):
        solution_generator.generate_solution()

    solution_generator.update_state("", "")

    solution, _ = solution_generator.generate_solution()
    assert solution == llm.responses[0]
    solution_generator.ai_model_agent.initial_prompt = "Test message 2"
    solution, _ = solution_generator.generate_solution()
    assert solution == llm.responses[1]
    solution_generator.ai_model_agent.initial_prompt = "Test message 3"
    solution, _ = solution_generator.generate_solution()
    assert solution == llm.responses[2]

    # Test history is intact
    assert solution_generator.messages[0].content == "Initial test message"
    assert solution_generator.messages[1].content == "This is a test response"
    assert solution_generator.messages[2].content == "Test message 2"
    assert solution_generator.messages[3].content == "Another test response"
    assert solution_generator.messages[4].content == "Test message 3"
    assert solution_generator.messages[5].content == "One more!"
