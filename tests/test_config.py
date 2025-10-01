# Author: Yiannis Charalambous 2023

from pytest import raises
from pydantic import ValidationError

from esbmc_ai.config import Config, AICustomModelConfig


def test_load_custom_ai() -> None:
    """Test loading custom AI models through config."""
    # Test valid custom AI config
    custom_config = AICustomModelConfig(
        max_tokens=4096,
        url="www.example.com",
        server_type="ollama",
    )

    assert custom_config.max_tokens == 4096
    assert custom_config.url == "www.example.com"
    assert custom_config.server_type == "ollama"


def test_load_custom_ai_fail() -> None:
    """Test that invalid custom AI configurations are rejected."""
    # Note: Pydantic v2 coerces strings to int when possible, so "1024" -> 1024
    # This is expected behavior and not an error

    # Missing max_tokens
    with raises(ValidationError):
        AICustomModelConfig(  # type: ignore
            url="www.example.com",
            server_type="ollama",
        )

    # Missing url
    with raises(ValidationError):
        AICustomModelConfig(  # type: ignore
            max_tokens=1000,
            server_type="ollama",
        )

    # Missing server type
    with raises(ValidationError):
        AICustomModelConfig(  # type: ignore
            max_tokens=100,
            url="www.example.com",
        )
