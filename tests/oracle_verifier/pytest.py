# Author: Yiannis Charalambous

"""Comprehensive test suite for CommandOracleOutputParser with pytest spec.

This module tests the CommandOracleOutputParser implementation with pytest output including:
- Output parsing with pytest_spec
- Issue extraction from collection errors
- Stack trace parsing from pytest output
- Error type and message extraction
- Successful vs failed verification detection
"""

from pathlib import Path

import pytest

from esbmc_ai.issue import Issue
from esbmc_ai.program_trace import ProgramTrace
from esbmc_ai.verifiers.cmd_oracle import (
    CommandOracleOutputParser,
    CommandOracleVerifierOutput,
    pytest_spec,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def multiple_errors_output() -> CommandOracleVerifierOutput:
    """Load the multiple.log sample with 2 collection errors."""
    with open("./tests/oracle_verifier/data/pytest/multiple.log") as file:
        parser = CommandOracleOutputParser(pytest_spec)
        return parser.parse_output(
            exit_success=0,
            return_code=1,
            duration=2.79,
            output=file.read(),
        )


@pytest.fixture(scope="module")
def multiple_errors_raw_output() -> str:
    """Load raw multiple.log output as string."""
    with open("./tests/oracle_verifier/data/pytest/multiple.log") as file:
        return file.read()


@pytest.fixture(scope="module")
def successful_output() -> CommandOracleVerifierOutput:
    """Load the successful.log sample."""
    with open("./tests/oracle_verifier/data/pytest/successful.log") as file:
        parser = CommandOracleOutputParser(pytest_spec)
        return parser.parse_output(
            exit_success=0,
            return_code=0,
            duration=2.03,
            output=file.read(),
        )


@pytest.fixture(scope="module")
def successful_raw_output() -> str:
    """Load raw successful.log output as string."""
    with open("./tests/oracle_verifier/data/pytest/successful.log") as file:
        return file.read()


@pytest.fixture(scope="module")
def collection_error_output() -> CommandOracleVerifierOutput:
    """Load the multiple_collection_error.log sample with 1 collection error."""
    with open(
        "./tests/oracle_verifier/data/pytest/multiple_collection_error.log"
    ) as file:
        parser = CommandOracleOutputParser(pytest_spec)
        return parser.parse_output(
            exit_success=0,
            return_code=1,
            duration=2.03,
            output=file.read(),
        )


@pytest.fixture(scope="module")
def collection_error_raw_output() -> str:
    """Load raw multiple_collection_error.log output as string."""
    with open(
        "./tests/oracle_verifier/data/pytest/multiple_collection_error.log"
    ) as file:
        return file.read()


# =============================================================================
# Tests for Successful Output
# =============================================================================


def test_successful_output_has_no_issues(
    successful_output: CommandOracleVerifierOutput,
) -> None:
    """Test that successful.log has 0 issues."""
    assert len(successful_output.issues) == 0


def test_successful_output_is_successful(
    successful_output: CommandOracleVerifierOutput,
) -> None:
    """Test that successful.log verification is successful."""
    assert successful_output.successful is True


# =============================================================================
# Tests for Multiple Errors Output
# =============================================================================


def test_multiple_errors_output_has_5_issues(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that multiple.log has 5 issues."""
    assert len(multiple_errors_output.issues) == 5


def test_multiple_errors_output_is_not_successful(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that multiple.log verification is not successful."""
    assert multiple_errors_output.successful is False


def test_multiple_errors_output_stack_traces(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that each issue has the correct stack trace location.

    Expected stack traces (1 trace point each due to low verbosity):
    - tests/test_ai_models.py:27
    - tests/test_esbmc.py:79
    - tests/test_esbmc.py:86
    - tests/test_esbmc.py:136
    - tests/test_singleton.py:46
    """
    expected_traces = [
        (Path("tests/test_ai_models.py"), 26),  # line 27, 0-based = 26
        (Path("tests/test_esbmc.py"), 78),  # line 79, 0-based = 78
        (Path("tests/test_esbmc.py"), 85),  # line 86, 0-based = 85
        (Path("tests/test_esbmc.py"), 135),  # line 136, 0-based = 135
        (Path("tests/test_singleton.py"), 45),  # line 46, 0-based = 45
    ]

    assert len(multiple_errors_output.issues) == len(expected_traces)

    for issue, (expected_path, expected_line_idx) in zip(
        multiple_errors_output.issues, expected_traces, strict=True
    ):
        # Each issue should have exactly 1 stack trace entry (low verbosity)
        assert len(issue.stack_trace) == 1
        trace = issue.stack_trace[0]
        assert trace.path == expected_path
        assert trace.line_idx == expected_line_idx


def test_multiple_errors_output_error_types(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that all issues have AssertionError as error type."""
    for issue in multiple_errors_output.issues:
        assert issue.error_type == "AssertionError"


def test_multiple_errors_output_severity(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that all issues have 'error' severity."""
    for issue in multiple_errors_output.issues:
        assert issue.severity == "error"


def test_multiple_errors_output_messages_not_empty(
    multiple_errors_output: CommandOracleVerifierOutput,
) -> None:
    """Test that all issues have non-empty messages."""
    for issue in multiple_errors_output.issues:
        assert issue.message, "Issue message should not be empty"


# =============================================================================
# Tests for Collection Error Output
# =============================================================================


def test_collection_error_output_has_1_issue(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that multiple_collection_error.log has 1 issue."""
    assert len(collection_error_output.issues) == 1


def test_collection_error_output_is_not_successful(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that collection error verification is not successful."""
    assert collection_error_output.successful is False


def test_collection_error_output_error_type(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that the collection error has SyntaxError as error type."""
    assert len(collection_error_output.issues) == 1
    assert collection_error_output.issues[0].error_type == "SyntaxError"


def test_collection_error_output_message(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that the collection error has the correct message."""
    assert len(collection_error_output.issues) == 1
    assert "'(' was never closed" in collection_error_output.issues[0].message


def test_collection_error_output_stack_trace(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that the collection error has a stack trace.

    Note: For collection errors, the stack trace contains pytest internal paths
    (the import chain), not the actual error location. The actual error location
    (tests/test_ai_models.py:14) is embedded in the error message lines with
    format 'E     File "path" line X'.
    """
    assert len(collection_error_output.issues) == 1
    issue = collection_error_output.issues[0]

    # Should have at least one stack trace entry (pytest internals)
    assert len(issue.stack_trace) >= 1

    # The first trace point should be from pytest's import mechanism
    first_trace = issue.stack_trace[0]
    assert first_trace.name == "importtestmodule"
    assert "_pytest" in str(first_trace.path)


def test_collection_error_output_severity(
    collection_error_output: CommandOracleVerifierOutput,
) -> None:
    """Test that the collection error has 'error' severity."""
    assert len(collection_error_output.issues) == 1
    assert collection_error_output.issues[0].severity == "error"
