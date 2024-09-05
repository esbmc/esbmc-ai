# Author: Yiannis Charalambous

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import FakeListLLM
import pytest

from esbmc_ai.ai_models import AIModel
from esbmc_ai.config import AIAgentConversation, ChatPromptSettings
from esbmc_ai.chats.solution_generator import SolutionGenerator


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

    solution_generator = SolutionGenerator(
        llm=llm,
        ai_model=model,
        ai_model_agent=chat_settings,
    )

    with pytest.raises(AssertionError):
        solution_generator.generate_solution()


def test_get_code_from_solution():
    assert (
        SolutionGenerator.get_code_from_solution(
            "This is a code block:\n\n```c\naaa\n```"
        )
        == "aaa"
    )

    assert (
        SolutionGenerator.get_code_from_solution(
            "This is a code block:\n\n```\nabc\n```"
        )
        == "abc"
    )

    # Edge case
    assert (
        SolutionGenerator.get_code_from_solution("This is a code block:```abc\n```")
        == ""
    )

    assert (
        SolutionGenerator.get_code_from_solution("The repaired C code is:\n\n```\n```")
        == ""
    )
