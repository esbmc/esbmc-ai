from esbmc_ai.command_runner import CommandRunner


def test_parse() -> None:
    sentence = 'Your sentence goes "here and \\"here\\" as well."'
    result = CommandRunner.parse_command(sentence)
    assert result == (
        "Your",
        [
            "sentence",
            "goes",
            '"here and \\"here\\" as well."',
        ],
    )


def test_parse_command() -> None:
    result = CommandRunner.parse_command("/fix-code")
    assert result == ("/fix-code", [])


def test_parse_command_args() -> None:
    result = CommandRunner.parse_command("/optimize-code main")
    assert result == ("/optimize-code", ["main"])
