# Author: Yiannis Charalambous

from pytest import raises

from esbmc_ai_lib.ai_models import (
    add_custom_ai_model,
    is_valid_ai_model,
    AIModel,
    AIModelProvider,
    AIModels,
    get_ai_model_by_name,
)


def test_is_valid_ai_model() -> None:
    assert is_valid_ai_model(AIModels.falcon_7b.value)
    assert is_valid_ai_model(AIModels.gpt_3_16k.value)
    assert is_valid_ai_model("gpt-3.5-turbo")
    assert is_valid_ai_model("falcon-7b")


def test_is_not_valid_ai_model() -> None:
    custom_model: AIModel = AIModel(
        name="custom_ai",
        tokens=999,
        provider=AIModelProvider.text_inference_server,
        url="www.example.com",
        config_message="{text}",
    )
    assert not is_valid_ai_model(custom_model)
    assert not is_valid_ai_model("doesn't exist")


def test_add_custom_ai_model() -> None:
    custom_model: AIModel = AIModel(
        name="custom_ai",
        tokens=999,
        provider=AIModelProvider.text_inference_server,
        url="www.example.com",
        config_message="{text}",
    )

    add_custom_ai_model(custom_model)

    assert is_valid_ai_model(custom_model.name)


def test_add_custom_ai_model_again() -> None:
    custom_model: AIModel = AIModel(
        name="custom_ai",
        tokens=999,
        provider=AIModelProvider.text_inference_server,
        url="www.example.com",
        config_message="{text}",
    )

    if is_valid_ai_model(custom_model.name):
        with raises(Exception):
            add_custom_ai_model(custom_model)

    assert is_valid_ai_model(custom_model.name)


def test_get_ai_model_by_name() -> None:
    # Try with first class AI
    assert get_ai_model_by_name("gpt-3.5-turbo")

    # Try with custom AI.
    # Add custom AI model if not added by previous tests.
    custom_model: AIModel = AIModel(
        name="custom_ai",
        tokens=999,
        provider=AIModelProvider.text_inference_server,
        url="www.example.com",
        config_message="{text}",
    )
    if not is_valid_ai_model(custom_model.name):
        add_custom_ai_model(custom_model)
    assert get_ai_model_by_name("custom_ai") is not None

    # Try with non existent.
    with raises(Exception):
        get_ai_model_by_name("not-exists")
