# Author: Yiannis Charalambous

from pathlib import Path
from langchain_core.language_models import FakeListChatModel
import pytest

from langchain.schema import AIMessage, HumanMessage, SystemMessage

from esbmc_ai.ai_models import AIModel
from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.chats.user_chat import UserChat
from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.verifiers.dummy_verifier import DummyVerifier
from esbmc_ai.verifiers.esbmc import ESBMC


@pytest.fixture(scope="function")
def setup():
    """Basic setup, uses a dummy system message, a dummy response from the LLM
    and also a dummy verifier."""
    system_messages: list = [
        SystemMessage(content="This is a system message"),
        AIMessage(content="OK"),
    ]

    verifier = DummyVerifier([], load_config=False)

    solution = Solution()
    solution.add_source_file(SourceFile(Path(""), Path(""), "This is source code"))

    summary_text = "THIS IS A SUMMARY OF THE CONVERSATION"
    chat: UserChat = UserChat(
        system_messages=system_messages,
        ai_model=AIModel(name="test", tokens=12),
        llm=FakeListChatModel(responses=[summary_text]),
        solution=solution,
        verifier=verifier,
        esbmc_output="This is esbmc output",
        set_solution_messages=[
            SystemMessage(content="Corrected output"),
        ],
    )

    return chat, summary_text, system_messages, verifier


@pytest.fixture
def initial_prompt():
    """Dummy initial prompt."""
    return "This is initial prompt"


def test_compress_message_stack(setup, initial_prompt) -> None:
    """Tests if the compress message stack function is called. Ensures the system
    messages are unaffects, and compression only occurs on the actual messages."""
    chat, summary_text, system_messages, _ = setup

    chat.messages = [SystemMessage(content=initial_prompt)]

    chat.compress_message_stack()

    # Check system messages
    for msg, chat_msg in zip(system_messages, chat._system_messages):
        assert msg.type == chat_msg.type and msg.content == chat_msg.content

    # Check normal messages
    assert chat.messages[0].content == summary_text


def test_finish_reason_lenght(setup, initial_prompt) -> None:
    """Tests the return of the finish reason of length. This is done by constructing
    a big prompt which is the initial prompt multiplied by a factor of 10"""
    chat, summary_text, system_messages, _ = setup

    # Make the prompt extra large.
    big_prompt: str = initial_prompt * 10

    response: ChatResponse = chat.send_message(big_prompt)

    assert response.finish_reason == FinishReason.length


def test_substitution() -> None:
    """Tests the substitution of the f-string variables in the system messages"""
    with open(
        "tests/samples/esbmc_output/line_test/cartpole_95_safe.c-amalgamation-80.c", "r"
    ) as file:
        esbmc_output: str = file.read()

    solution = Solution()
    solution.add_source_file(SourceFile(Path(""), Path(""), "11111"))

    # This test is designed to work with ESBMC as it uses ESBMC output as a test
    # sample. So get error line and type work using ESBMC.
    chat = UserChat(
        solution=solution,
        ai_model=AIModel("test", 1000),
        system_messages=[
            SystemMessage(content="{source_code}{esbmc_output}{error_line}{error_type}")
        ],
        esbmc_output=esbmc_output,
        verifier=ESBMC(),
        llm=FakeListChatModel(responses=["THIS IS A SUMMARY OF THE CONVERSATION"]),
        set_solution_messages=[HumanMessage(content="")],
    )

    assert (
        chat._system_messages[0].content
        == "11111"
        + esbmc_output
        + str(285)
        + "dereference failure: Access to object out of bounds"
    )
