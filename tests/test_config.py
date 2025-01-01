# Author: Yiannis Charalambous 2023

from pytest import raises

from esbmc_ai.config import Config
from esbmc_ai.ai_models import is_valid_ai_model


def test_load_custom_ai() -> None:
    custom_ai_config: dict = {
        "example_ai": {
            "max_tokens": 4096,
            "url": "www.example.com",
            "server_type": "ollama",
        }
    }

    Config()._load_custom_ai(custom_ai_config)

    assert is_valid_ai_model("example_ai")


def test_load_custom_ai_fail() -> None:
    # Wrong max_tokens type
    ai_conf: dict = {
        "example_ai_2": {
            "max_tokens": "1024",
            "url": "www.example.com",
            "server_type": "ollama",
        }
    }

    with raises(TypeError):
        Config()._validate_custom_ai(ai_conf)

    # Wrong max_tokens value
    ai_conf: dict = {
        "example_ai_2": {
            "max_tokens": 0,
            "url": "www.example.com",
            "server_type": "ollama",
        }
    }

    with raises(ValueError):
        Config()._validate_custom_ai(ai_conf)

    # Missing max_tokens
    ai_conf: dict = {
        "example_ai_2": {
            "url": "www.example.com",
            "server_type": "ollama",
        }
    }

    with raises(KeyError):
        Config()._validate_custom_ai(ai_conf)

    # Missing url
    ai_conf: dict = {
        "example_ai_2": {
            "max_tokens": 1000,
            "server_type": "ollama",
        }
    }

    with raises(KeyError):
        Config()._validate_custom_ai(ai_conf)

    # Missing server type
    ai_conf: dict = {
        "example_ai_2": {
            "max_tokens": 100,
            "url": "www.example.com",
        }
    }

    with raises(KeyError):
        Config()._validate_custom_ai(ai_conf)

    # Test load empty
    ai_conf: dict = {}

    Config()._validate_custom_ai(ai_conf)
