# Author: Yiannis Charalambous

from typing import Optional
import pytest

from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain_community.llms.fake import FakeListLLM

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings
from esbmc_ai.latest_state_solution_generator import LatestStateSolutionGenerator


@pytest.fixture(scope="function")
def setup_llm_model():
    llm = FakeListLLM(
        responses=[
            "This is a test response",
            "Another test response",
            "One more!",
        ],
    )
    model = AIModel("test model", 1000)
    return llm, model


def test_call_update_state_first(setup_llm_model) -> None:
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


def test_functionality(setup_llm_model) -> None:
    """Test functionality to see if the latest state along with system messages
    are passed to send_message only."""

    def mocked_send_message(message: Optional[str] = None) -> ChatResponse:
        assert len(solution_generator.messages) == 1
        assert solution_generator.messages[0] == HumanMessage(
            content="Initial test message"
        )
        return ChatResponse()

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

    solution_generator.update_state("", "")

    solution_generator.send_message = mocked_send_message
    solution_generator.generate_solution()


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
