# Author: Yiannis Charalambous

from langchain.prompts.chat import ChatPromptValue
from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    PromptValue,
    SystemMessage,
)
from pytest import raises

from esbmc_ai.ai_models import (
    AIModelOpenAI,
    add_custom_ai_model,
    is_valid_ai_model,
    AIModel,
    get_ai_model_by_name,
)


class MockAIModel(AIModel):
    """Used to test AIModels, it implements some mock versions of abstract
    methods."""

    def get_num_tokens(self, content: str) -> int:
        _ = content
        return len(content)

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        _ = messages
        return sum(len(str(msg.content)) for msg in messages)


def test_is_not_valid_ai_model() -> None:
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )
    assert not is_valid_ai_model(custom_model)
    assert not is_valid_ai_model("doesn't exist")


def test_add_custom_ai_model() -> None:
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )

    add_custom_ai_model(custom_model)

    assert is_valid_ai_model(custom_model.name)

    # Test add again.

    if is_valid_ai_model(custom_model.name):
        with raises(Exception):
            add_custom_ai_model(custom_model)

    assert is_valid_ai_model(custom_model.name)


def test_get_ai_model_by_name() -> None:
    # Try with first class AI
    # assert get_ai_model_by_name("falcon-7b")

    # Try with custom AI.
    # Add custom AI model if not added by previous tests.
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )
    if not is_valid_ai_model(custom_model.name):
        add_custom_ai_model(custom_model)
    assert get_ai_model_by_name("custom_ai") is not None

    # Try with non existent.
    with raises(Exception):
        get_ai_model_by_name("not-exists")


def test_apply_chat_template() -> None:
    messages: list = [
        SystemMessage(content="M1"),
        HumanMessage(content="M2"),
        AIMessage(content="M3"),
    ]

    # Test the identity method.
    custom_model_1: MockAIModel = MockAIModel(
        name="custom",
        tokens=999,
    )

    prompt: PromptValue = custom_model_1.apply_chat_template(messages=messages)

    assert prompt == ChatPromptValue(messages=messages)


def test_escape_messages() -> None:
    """Tests that the brackets are escaped properly using `AIModel.escape_message`."""

    messages = [
        HumanMessage(content="Hello my name is {name} and I like {{apples}}"),
        SystemMessage(content="Hello my {{name is system} and I like {{{apples}}}"),
        AIMessage(content="Hello my {{ {{{apples}}"),
        SystemMessage(content="{descreption}{descreption}{{descreption}}{descreption}"),
        SystemMessage(content="{descreption}{{{descreption}}}{{{{{descreption}}}}}"),
        SystemMessage(
            content="{apples}{{{apples}}}{{{{{apples}}}}}{{{{{{{apples}}}}}}}"
        ),
    ]

    allowed = ["name", "descreption"]

    filtered = [
        HumanMessage(content="Hello my name is {name} and I like {{apples}}"),
        SystemMessage(content="Hello my {{name is system}} and I like {{{{apples}}}}"),
        AIMessage(content="Hello my {{ {{{{apples}}"),
        SystemMessage(content="{descreption}{descreption}{{descreption}}{descreption}"),
        SystemMessage(content="{descreption}{{{descreption}}}{{{{{descreption}}}}}"),
        SystemMessage(
            content="{{apples}}{{{{apples}}}}{{{{{{apples}}}}}}{{{{{{{{apples}}}}}}}}"
        ),
    ]

    result = list(MockAIModel.escape_messages(messages, allowed))

    assert result[0] == filtered[0]
    assert result[1] == filtered[1]
    assert result[2] == filtered[2]
    assert result[3] == filtered[3]
    assert result[4] == filtered[4]
    assert result[5] == filtered[5]


def test__get_openai_model_max_tokens() -> None:
    assert AIModelOpenAI.get_openai_model_max_tokens("gpt-4o") == 128000
    assert AIModelOpenAI.get_openai_model_max_tokens("gpt-4-turbo") == 8192
    assert AIModelOpenAI.get_openai_model_max_tokens("gpt-3.5-turbo") == 16385
    assert AIModelOpenAI.get_openai_model_max_tokens("gpt-3.5-turbo-instruct") == 4096
    assert AIModelOpenAI.get_openai_model_max_tokens("gpt-3.5-turbo-aaaaaa") == 16385
    assert (
        AIModelOpenAI.get_openai_model_max_tokens("gpt-3.5-turbo-instruct-bbb") == 4096
    )

    with raises(ValueError):
        AIModelOpenAI.get_openai_model_max_tokens("aaaaa")
