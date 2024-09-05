# Author: Yiannis Charalambous

import pytest
from esbmc_ai.solution import Solution, SourceFile

#####################################
# Solution
#####################################


@pytest.fixture(scope="function")
def solution() -> Solution:
    return Solution()


def test_add_source_file(solution) -> None:
    src: str = "int main(int argc, char** argv) {return 0;}"
    solution.add_source_file(None, src)
    assert (
        len(solution.files) == 1
        and solution.files[0].file_path == None
        and solution.files[0].latest_content == src
    )
    src = '#include <stdio.h> int main(int argc, char** argv) { printf("hello world\n"); return 0;}'
    solution.add_source_file("Testfile1", src)
    assert (
        len(solution.files) == 2
        and solution.files[1].file_path == "Testfile1"
        and solution.files[1].latest_content == src
    )
    assert (
        len(solution.files_mapped) == 1
        and solution.files_mapped["Testfile1"].file_path == "Testfile1"
        and solution.files_mapped["Testfile1"].initial_content == src
    )


#####################################
# SourceFile
#####################################


def test_apply_line_patch() -> None:
    text = "\n".join(["a", "b", "c", "d", "e", "f", "g"])
    answer = "\n".join(["a", "b", "1", "g"])
    assert SourceFile.apply_line_patch(text, "1", 2, 5) == answer

    text = "\n".join(["a", "b", "c", "d", "e", "f", "g"])
    answer = "\n".join(["a", "b", "c", "1", "e", "f", "g"])
    assert SourceFile.apply_line_patch(text, "1", 3, 3) == answer
