# Author: Yiannis Charalambous

from esbmc_ai.solution import SourceFile


def test_apply_line_patch() -> None:
    text = "\n".join(["a", "b", "c", "d", "e", "f", "g"])
    answer = "\n".join(["a", "b", "1", "g"])
    assert SourceFile.apply_line_patch(text, "1", 2, 5) == answer

    text = "\n".join(["a", "b", "c", "d", "e", "f", "g"])
    answer = "\n".join(["a", "b", "c", "1", "e", "f", "g"])
    assert SourceFile.apply_line_patch(text, "1", 3, 3) == answer


# TODO Add more tests for solution and sourcefile
