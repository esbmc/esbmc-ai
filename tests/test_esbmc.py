# Author: Yiannis Charalambous

from esbmc_ai.verifiers.esbmc import ESBMCOutput, ESBMCOutputParser
from esbmc_ai.issue import Issue, VerifierIssue
from pathlib import Path
import pytest


@pytest.fixture(scope="module")
def bubble_sort_output() -> ESBMCOutput:
    """Load the bubble_sort.txt sample output with stack trace."""
    with open("./tests/samples/esbmc_output/bubble_sort.txt") as file:
        return ESBMCOutputParser.parse_output(
            return_code=1,
            output=file.read(),
        )


def test_get_source_code_err_line(bubble_sort_output: ESBMCOutput) -> None:
    """Test that error line numbers are correctly parsed from ESBMC output."""
    # The error in bubble_sort.txt is at line 7
    assert len(bubble_sort_output.issues) == 1
    assert bubble_sort_output.issues[0].line_number == 7


def test_esbmc_get_counter_example(bubble_sort_output: ESBMCOutput) -> None:
    """Test that counterexamples are correctly parsed into VerifierIssue objects."""
    # Verify output contains counterexample marker
    assert "[Counterexample]" in bubble_sort_output.output

    # Verify exactly one issue was parsed
    assert len(bubble_sort_output.issues) == 1

    # Verify the issue is a VerifierIssue (has counterexample)
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify counterexample contains trace data
    assert len(issue.counterexample) > 0

    # Verify stack_trace also contains data (from --show-stacktrace)
    assert len(issue.stack_trace) > 0


def test_esbmc_parse_stack_trace(bubble_sort_output: ESBMCOutput) -> None:
    """Test that stack trace from --show-stacktrace is correctly parsed."""
    assert len(bubble_sort_output.issues) == 1
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # The stack trace should show the call from main to buggy_bubble_sort
    # According to bubble_sort.txt line 105: "at file samples/bubble_sort.c line 19 column 3 function main"
    assert len(issue.stack_trace) > 0

    # First trace should be the call from main (line 19, function main)
    first_trace = issue.stack_trace[0]
    assert first_trace.line_idx == 18  # 0-based, so line 19 -> index 18
    assert first_trace.name == "main"
    assert first_trace.path == Path("samples/bubble_sort.c")


def test_esbmc_get_violated_property(bubble_sort_output: ESBMCOutput) -> None:
    """Test that violated property is correctly extracted."""
    violated_prop = ESBMCOutputParser.get_violated_property(bubble_sort_output.output)
    assert violated_prop is not None

    # The violated property should contain the expected sections
    assert "Violated property:" in violated_prop
    assert "file samples/bubble_sort.c line 7" in violated_prop


@pytest.fixture(scope="module")
def clang_parse_error_output() -> ESBMCOutput:
    """Load the threading.c clang parse error sample."""
    with open("./tests/samples/esbmc_output/clang_parse_errors/threading.txt") as file:
        return ESBMCOutputParser.parse_output(
            output=file.read(),
            return_code=1,
        )


def test_get_clang_err_line_index(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that compilation error line numbers are correctly parsed."""
    # Verify parsing error was detected
    assert "ERROR: PARSING ERROR" in clang_parse_error_output.output

    # Verify at least one issue was parsed
    assert len(clang_parse_error_output.issues) >= 1

    # Find the issue for line 26
    line_26_issue = None
    for issue in clang_parse_error_output.issues:
        assert isinstance(issue, Issue)
        assert issue.error_type == "Compilation Error"
        if issue.line_number == 26:
            line_26_issue = issue
            break

    assert line_26_issue is not None, "Expected to find compilation error at line 26"


def test_esbmc_output_sections(bubble_sort_output: ESBMCOutput) -> None:
    """Test if the sections are right."""
    stack_trace: str = """c:@F@buggy_bubble_sort at file samples/bubble_sort.c line 19 column 3 function main
c:@F@main"""
    violated_property: str = """dereference failure: array bounds violated"""
    counterexample: str = """[Counterexample]


State 1 file samples/bubble_sort.c line 7 column 7 function buggy_bubble_sort thread 0
----------------------------------------------------
Violated property:
  file samples/bubble_sort.c line 7 column 7 function buggy_bubble_sort
Stack trace:
  c:@F@buggy_bubble_sort at file samples/bubble_sort.c line 19 column 3 function main
  c:@F@main
  dereference failure: array bounds violated


VERIFICATION FAILED

Bug found (k = 5)"""
    assert bubble_sort_output.sections.stack_trace == stack_trace
    assert bubble_sort_output.sections.violated_property == violated_property
    assert bubble_sort_output.sections.counterexample == counterexample
