# Author: Yiannis Charalambous

from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import (
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from esbmc_ai.config import default_scenario
from esbmc_ai.ai_models import AIModel
from esbmc_ai.reverse_order_solution_generator import ReverseOrderSolutionGenerator


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
    # TODO Test the send_message method to ensure it actually reverses the
    # messages as intended.
    pass


def test_message_stack(setup_llm_model) -> None:
    llm, model = setup_llm_model

    solution_generator = ReverseOrderSolutionGenerator(
        llm=llm,
        ai_model=model,
        scenarios={
            "base": {
                "initial": "Initial test message",
                "system": (
                    SystemMessage(content="Test message 1"),
                    HumanMessage(content="Test message 2"),
                    AIMessage(content="Test message 3"),
                ),
            }
        },
    )

    with pytest.raises(AssertionError):
        solution_generator.generate_solution()

    solution_generator.update_state("", "")

    solution, _ = solution_generator.generate_solution(ignore_system_message=True)
    assert solution == llm.responses[0]
    solution_generator.scenarios[default_scenario]["initial"] = "Test message 2"
    solution, _ = solution_generator.generate_solution(ignore_system_message=True)
    assert solution == llm.responses[1]
    solution_generator.scenarios[default_scenario]["initial"] = "Test message 3"
    solution, _ = solution_generator.generate_solution(ignore_system_message=True)
    assert solution == llm.responses[2]

    # Test history is intact
    assert solution_generator.messages[0].content == "Initial test message"
    assert solution_generator.messages[1].content == "This is a test response"
    assert solution_generator.messages[2].content == "Test message 2"
    assert solution_generator.messages[3].content == "Another test response"
    assert solution_generator.messages[4].content == "Test message 3"
    assert solution_generator.messages[5].content == "One more!"
