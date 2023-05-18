# Author: Yiannis Charalambous 2023

import pytest

import esbmc_ai_lib.config as config


def test_load_config_value() -> None:
    result, ok = config._load_config_value(
        {
            "test": "value",
        },
        "test",
    )
    assert ok and result == "value"


def test_load_config_value_default_value() -> None:
    result, ok = config._load_config_value(
        {
            "test": "value",
        },
        "test",
        "wrong",
    )
    assert ok and result == "value"


def test_load_config_value_default_value_not_exists() -> None:
    result, ok = config._load_config_value(
        {},
        "test2",
        "wrong",
    )
    assert not ok and result == "wrong"


def test_load_config_real_number() -> None:
    result = config._load_config_real_number(
        {
            "test": 1.0,
        },
        "test",
    )
    assert result == 1.0


def test_load_config_real_number_default_value() -> None:
    result = config._load_config_real_number({}, "test", 1.1)
    assert result == 1.1


def test_load_config_real_number_wrong_value() -> None:
    with pytest.raises(TypeError):
        result = config._load_config_real_number(
            {
                "test": "wrong value",
            },
            "test",
        )
        assert result == None


def test_load_config_real_number_wrong_value_default() -> None:
    with pytest.raises(TypeError):
        result = config._load_config_real_number(
            {
                "test": "wrong value",
            },
            "test",
            1.0,
        )
        assert result == None
