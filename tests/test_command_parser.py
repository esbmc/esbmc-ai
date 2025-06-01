# Author: Yiannis Charalambous

from esbmc_ai.component_loader import ComponentLoader


def test_parse() -> None:
    sentence = 'Your sentence goes "here and \\"here\\" as well."'
    result = ComponentLoader.parse_command(sentence)
    assert result == (
        "Your",
        [
            "sentence",
            "goes",
            '"here and \\"here\\" as well."',
        ],
    )


def test_parse_command() -> None:
    result = ComponentLoader.parse_command("/fix-code")
    assert result == ("/fix-code", [])


def test_parse_command_args() -> None:
    result = ComponentLoader.parse_command("/optimize-code main")
    assert result == ("/optimize-code", ["main"])
