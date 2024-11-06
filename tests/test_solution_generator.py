# Author: Yiannis Charalambous

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import FakeListChatModel, FakeListLLM
import pytest

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chats.solution_generator import SolutionGenerator
from esbmc_ai.config import FixCodeScenarios


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

    solution_generator = SolutionGenerator(
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


def test_substitution() -> None:
    with open(
        "tests/samples/esbmc_output/line_test/cartpole_95_safe.c-amalgamation-80.c", "r"
    ) as file:
        esbmc_output: str = file.read()

    chat = SolutionGenerator(
        scenarios={
            "base": {
                "initial": "{source_code}{esbmc_output}{error_line}{error_type}",
                "system": (
                    SystemMessage(
                        content="System:{source_code}{esbmc_output}{error_line}{error_type}"
                    ),
                ),
            }
        },
        ai_model=AIModel("test", 10000000),
        llm=FakeListChatModel(responses=["22222", "33333"]),
        source_code_format="full",
        esbmc_output_type="full",
    )

    chat.update_state("11111", esbmc_output)
    chat.generate_solution(ignore_system_message=False)

    assert (
        chat.messages[0].content
        == "System:11111"
        + esbmc_output
        + str(285)
        + "dereference failure: Access to object out of bounds"
    )

    assert chat.messages[1].content == "22222"

    chat.update_state("11111", esbmc_output)
    chat.generate_solution(ignore_system_message=False)

    assert (
        chat.messages[2].content
        == "11111"
        + esbmc_output
        + str(285)
        + "dereference failure: Access to object out of bounds"
    )

    assert chat.messages[3].content == "33333"
