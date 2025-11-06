# Author: Yiannis Charalambous

"""Comprehensive test suite for ESBMC verifier implementation.

This module tests all aspects of the ESBMC verifier integration including:
- Output parsing (ESBMCOutputParser)
- Section extraction (ESBMCOutputSections)
- Issue creation and validation
- Stack trace and counterexample parsing
- Error handling for various output formats
"""

from esbmc_ai.verifiers.esbmc import ESBMCOutput, ESBMCOutputParser, ESBMCOutputSections
from esbmc_ai.issue import Issue, VerifierIssue
from esbmc_ai.program_trace import ProgramTrace
from pathlib import Path
import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def bubble_sort_output() -> ESBMCOutput:
    """Load the bubble_sort.txt sample output with stack trace."""
    with open("./tests/samples/esbmc_output/bubble_sort.txt") as file:
        return ESBMCOutputParser.parse_output(
            return_code=1,
            output=file.read(),
        )


@pytest.fixture(scope="module")
def bubble_sort_raw_output() -> str:
    """Load raw bubble_sort.txt output as string."""
    with open("./tests/samples/esbmc_output/bubble_sort.txt") as file:
        return file.read()


@pytest.fixture(scope="module")
def clang_parse_error_output() -> ESBMCOutput:
    """Load the threading.c clang parse error sample."""
    with open("./tests/samples/esbmc_output/clang_parse_errors/threading.txt") as file:
        return ESBMCOutputParser.parse_output(
            output=file.read(),
            return_code=1,
        )


@pytest.fixture(scope="module")
def clang_parse_error_raw_output() -> str:
    """Load raw threading.txt output as string."""
    with open("./tests/samples/esbmc_output/clang_parse_errors/threading.txt") as file:
        return file.read()


# =============================================================================
# ESBMCOutput Tests - Basic Properties
# =============================================================================


def test_esbmc_output_successful_property_failure(bubble_sort_output: ESBMCOutput) -> None:
    """Test that verification failure is correctly identified."""
    assert bubble_sort_output.return_code == 1
    assert not bubble_sort_output.successful


def test_esbmc_output_successful_property_success() -> None:
    """Test that verification success is correctly identified."""
    output = ESBMCOutputParser.parse_output(
        return_code=0,
        output="VERIFICATION SUCCESSFUL",
    )
    assert output.successful
    assert output.return_code == 0


def test_esbmc_output_has_output_text(bubble_sort_output: ESBMCOutput) -> None:
    """Test that raw output text is preserved."""
    assert bubble_sort_output.output
    assert "ESBMC version" in bubble_sort_output.output
    assert "[Counterexample]" in bubble_sort_output.output


def test_esbmc_output_duration() -> None:
    """Test that duration is correctly stored."""
    output = ESBMCOutputParser.parse_output(
        return_code=0,
        output="test",
        duration=1.5,
    )
    assert output.duration == 1.5


# =============================================================================
# ESBMCOutputParser Tests - Basic Parsing
# =============================================================================


def test_parse_output_creates_esbmc_output() -> None:
    """Test that parse_output returns ESBMCOutput object."""
    output = ESBMCOutputParser.parse_output(
        return_code=0,
        output="test output",
    )
    assert isinstance(output, ESBMCOutput)
    assert output.return_code == 0
    assert output.output == "test output"


def test_parse_output_no_issues() -> None:
    """Test parsing output with no verification issues."""
    output = ESBMCOutputParser.parse_output(
        return_code=0,
        output="VERIFICATION SUCCESSFUL\nNo issues found",
    )
    assert len(output.issues) == 0


def test_parse_output_with_counterexample(bubble_sort_output: ESBMCOutput) -> None:
    """Test that counterexample is detected and parsed."""
    assert len(bubble_sort_output.issues) == 1
    assert isinstance(bubble_sort_output.issues[0], VerifierIssue)


def test_parse_output_with_parsing_error(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that parsing errors are correctly detected."""
    assert len(clang_parse_error_output.issues) >= 1
    # Parsing errors should create regular Issue objects, not VerifierIssue
    for issue in clang_parse_error_output.issues:
        assert isinstance(issue, Issue)
        assert issue.error_type == "Compilation Error"


# =============================================================================
# ESBMCOutputParser Tests - Issue Parsing
# =============================================================================


def test_parse_verification_failure_creates_verifier_issue(
    bubble_sort_output: ESBMCOutput,
) -> None:
    """Test that verification failures create VerifierIssue objects."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)
    assert issue.error_type
    assert issue.message
    assert len(issue.stack_trace) > 0
    assert len(issue.counterexample) >= 0


def test_issue_has_error_type(bubble_sort_output: ESBMCOutput) -> None:
    """Test that issue has correct error type."""
    issue = bubble_sort_output.issues[0]
    assert issue.error_type == "dereference failure: array bounds violated"


def test_issue_has_message(bubble_sort_output: ESBMCOutput) -> None:
    """Test that issue has a message."""
    issue = bubble_sort_output.issues[0]
    assert issue.message
    # Message should contain the violated property
    assert "file samples/bubble_sort.c line 7" in issue.message


def test_issue_has_severity(bubble_sort_output: ESBMCOutput) -> None:
    """Test that issue has correct severity."""
    issue = bubble_sort_output.issues[0]
    assert issue.severity == "error"


def test_issue_convenience_properties(bubble_sort_output: ESBMCOutput) -> None:
    """Test Issue convenience properties for accessing location info."""
    issue = bubble_sort_output.issues[0]
    assert issue.line_number == 7  # 1-based
    assert issue.line_index == 6  # 0-based
    assert issue.file_path == Path("samples/bubble_sort.c")
    assert issue.function_name == "buggy_bubble_sort"


# =============================================================================
# ESBMCOutputParser Tests - Stack Trace Parsing
# =============================================================================


def test_parse_stack_trace(bubble_sort_output: ESBMCOutput) -> None:
    """Test that stack trace from --show-stacktrace is correctly parsed."""
    assert len(bubble_sort_output.issues) == 1
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # The stack trace should show the call from main to buggy_bubble_sort
    assert len(issue.stack_trace) > 0


def test_stack_trace_has_correct_structure(bubble_sort_output: ESBMCOutput) -> None:
    """Test that stack trace has correct structure."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify each trace has required fields
    for trace in issue.stack_trace:
        assert isinstance(trace, ProgramTrace)
        assert isinstance(trace.path, Path)
        assert isinstance(trace.line_idx, int)
        assert trace.line_idx >= 0  # Should be 0-based


def test_stack_trace_caller_location(bubble_sort_output: ESBMCOutput) -> None:
    """Test that first stack trace entry shows the caller location."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # First trace should be the call from main (line 19, function main)
    first_trace = issue.stack_trace[0]
    assert first_trace.line_idx == 18  # 0-based, so line 19 -> index 18
    assert first_trace.name == "main"
    assert first_trace.path == Path("samples/bubble_sort.c")


def test_stack_trace_error_location(bubble_sort_output: ESBMCOutput) -> None:
    """Test that last stack trace entry shows the error location."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Last trace should be the error location (line 7, function buggy_bubble_sort)
    last_trace = issue.stack_trace[-1]
    assert last_trace.line_idx == 6  # 0-based, so line 7 -> index 6
    assert last_trace.name == "buggy_bubble_sort"
    assert last_trace.path == Path("samples/bubble_sort.c")


def test_stack_trace_order(bubble_sort_output: ESBMCOutput) -> None:
    """Test that stack trace is in correct order (caller to callee)."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify trace indices are sequential
    for i, trace in enumerate(issue.stack_trace):
        assert trace.trace_index == i


# =============================================================================
# ESBMCOutputParser Tests - Counterexample Parsing
# =============================================================================


def test_parse_counterexample_traces(bubble_sort_output: ESBMCOutput) -> None:
    """Test that counterexample traces are correctly parsed."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify counterexample contains trace data
    assert len(issue.counterexample) > 0


def test_counterexample_has_correct_structure(bubble_sort_output: ESBMCOutput) -> None:
    """Test that counterexample traces have correct structure."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify each trace has required fields
    for trace in issue.counterexample:
        assert isinstance(trace, ProgramTrace)
        assert isinstance(trace.path, Path)
        assert isinstance(trace.line_idx, int)
        assert trace.line_idx >= 0  # Should be 0-based


def test_counterexample_trace_indices(bubble_sort_output: ESBMCOutput) -> None:
    """Test that counterexample trace indices are sequential."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Verify trace indices are sequential
    for i, trace in enumerate(issue.counterexample):
        assert trace.trace_index == i


def test_counterexample_contains_error_location(
    bubble_sort_output: ESBMCOutput,
) -> None:
    """Test that counterexample includes the error location."""
    issue = bubble_sort_output.issues[0]
    assert isinstance(issue, VerifierIssue)

    # Find the error location in counterexample (line 7)
    error_traces = [t for t in issue.counterexample if t.line_idx == 6]
    assert len(error_traces) > 0


# =============================================================================
# ESBMCOutputParser Tests - Split Counterexample Sections
# =============================================================================


def test_split_counterexample_sections_single(bubble_sort_raw_output: str) -> None:
    """Test splitting output with single counterexample."""
    sections = ESBMCOutputParser._split_counterexample_sections(bubble_sort_raw_output)
    assert len(sections) == 1
    assert sections[0].startswith("[Counterexample]")


def test_split_counterexample_sections_none() -> None:
    """Test splitting output with no counterexample."""
    sections = ESBMCOutputParser._split_counterexample_sections(
        "VERIFICATION SUCCESSFUL"
    )
    assert len(sections) == 0


def test_split_counterexample_sections_multiple() -> None:
    """Test splitting output with multiple counterexamples."""
    output = "[Counterexample]\nError 1\n[Counterexample]\nError 2"
    sections = ESBMCOutputParser._split_counterexample_sections(output)
    assert len(sections) == 2
    assert sections[0].startswith("[Counterexample]")
    assert "Error 1" in sections[0]
    assert sections[1].startswith("[Counterexample]")
    assert "Error 2" in sections[1]


# =============================================================================
# ESBMCOutputParser Tests - Error Type Extraction
# =============================================================================


def test_extract_error_type(bubble_sort_raw_output: str) -> None:
    """Test error type extraction from violated property."""
    error_type = ESBMCOutputParser._extract_error_type(bubble_sort_raw_output)
    assert error_type == "dereference failure: array bounds violated"


def test_extract_error_type_not_found() -> None:
    """Test error type extraction when not found."""
    error_type = ESBMCOutputParser._extract_error_type("No violated property")
    assert error_type is None


def test_extract_error_type_incomplete_output() -> None:
    """Test error type extraction with incomplete output."""
    output = "Violated property:\n"
    error_type = ESBMCOutputParser._extract_error_type(output)
    assert error_type is None


# =============================================================================
# ESBMCOutputParser Tests - Violated Property Extraction
# =============================================================================


def test_extract_violated_property_section(bubble_sort_raw_output: str) -> None:
    """Test violated property section extraction."""
    section = ESBMCOutputParser._extract_violated_property_section(
        bubble_sort_raw_output
    )
    assert section is not None
    assert "Violated property:" in section
    assert "file samples/bubble_sort.c line 7" in section


def test_extract_violated_property_section_not_found() -> None:
    """Test violated property extraction when not found."""
    section = ESBMCOutputParser._extract_violated_property_section(
        "No violated property"
    )
    assert section is None


# =============================================================================
# ESBMCOutputParser Tests - Trace Line Parsing
# =============================================================================


def test_parse_trace_line_complete() -> None:
    """Test parsing complete trace line with all fields."""
    line = (
        "State 1 file test.c line 10 column 5 function main thread 0\n"
        "----------------------------------------------------\n"
        "x = 5\n"
    )
    result = ESBMCOutputParser._parse_trace_line(line)
    assert result is not None
    assert result.state_number == 1
    assert result.filename == Path("test.c")
    assert result.line_number == 10
    assert result.method_name == "main"
    assert result.thread_index == 0


def test_parse_trace_line_without_function() -> None:
    """Test parsing trace line without function name."""
    line = (
        "State 1 file test.c line 10 column 5 thread 0\n"
        "----------------------------------------------------\n"
        "x = 5\n"
    )
    result = ESBMCOutputParser._parse_trace_line(line)
    assert result is not None
    assert result.method_name == ""


def test_parse_trace_line_invalid_format() -> None:
    """Test parsing trace line with invalid format."""
    line = "Invalid trace line\n"
    with pytest.raises(ValueError):
        ESBMCOutputParser._parse_trace_line(line)


def test_parse_trace_line_missing_required_fields() -> None:
    """Test parsing trace line with missing required fields."""
    line = "State 1 thread 0\n----\nerror\n"
    with pytest.raises(ValueError):
        ESBMCOutputParser._parse_trace_line(line)


# =============================================================================
# ESBMCOutputSections Tests
# =============================================================================


def test_esbmc_output_sections_from_output(bubble_sort_output: ESBMCOutput) -> None:
    """Test ESBMCOutputSections construction from output."""
    sections = bubble_sort_output.sections
    assert isinstance(sections, ESBMCOutputSections)
    assert sections.violated_property is not None
    assert sections.counterexample is not None
    assert sections.stack_trace is not None


def test_sections_violated_property(bubble_sort_output: ESBMCOutput) -> None:
    """Test violated property section extraction."""
    sections = bubble_sort_output.sections
    assert sections.violated_property is not None
    assert sections.violated_property == "dereference failure: array bounds violated"


def test_sections_counterexample(bubble_sort_output: ESBMCOutput) -> None:
    """Test counterexample section extraction."""
    sections = bubble_sort_output.sections
    assert sections.counterexample is not None
    assert "[Counterexample]" in sections.counterexample
    assert "State 1" in sections.counterexample
    assert "VERIFICATION FAILED" in sections.counterexample


def test_sections_stack_trace(bubble_sort_output: ESBMCOutput) -> None:
    """Test stack trace section extraction."""
    sections = bubble_sort_output.sections
    assert sections.stack_trace is not None
    assert "c:@F@buggy_bubble_sort" in sections.stack_trace
    assert "c:@F@main" in sections.stack_trace


def test_sections_immutable(bubble_sort_output: ESBMCOutput) -> None:
    """Test that ESBMCOutputSections is immutable (frozen)."""
    sections = bubble_sort_output.sections
    with pytest.raises(Exception):  # Pydantic will raise ValidationError
        sections.violated_property = "changed"  # type: ignore


def test_sections_cached_property(bubble_sort_output: ESBMCOutput) -> None:
    """Test that sections property is cached."""
    sections1 = bubble_sort_output.sections
    sections2 = bubble_sort_output.sections
    # Should be the same object instance due to caching
    assert sections1 is sections2


def test_sections_no_counterexample() -> None:
    """Test sections when output has no counterexample."""
    output = ESBMCOutputParser.parse_output(
        return_code=0,
        output="VERIFICATION SUCCESSFUL",
    )
    sections = output.sections
    assert sections.counterexample is None
    assert sections.violated_property is None
    assert sections.stack_trace is None


def test_sections_no_stack_trace() -> None:
    """Test sections when output has no stack trace."""
    output_text = (
        "[Counterexample]\n"
        "State 1 file test.c line 5 column 3 function main thread 0\n"
        "----\n"
        "error\n"
    )
    output = ESBMCOutputParser.parse_output(return_code=1, output=output_text)
    sections = output.sections
    assert sections.counterexample is not None
    # No "Stack trace:" marker, so these will be None
    assert sections.violated_property is None
    assert sections.stack_trace is None


# =============================================================================
# Compilation Error Tests
# =============================================================================


def test_clang_parse_error_detected(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that compilation error is detected."""
    assert "ERROR: PARSING ERROR" in clang_parse_error_output.output


def test_clang_parse_error_creates_issues(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that compilation errors create Issue objects."""
    assert len(clang_parse_error_output.issues) >= 1


def test_clang_parse_error_issue_type(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that compilation errors have correct type."""
    for issue in clang_parse_error_output.issues:
        assert isinstance(issue, Issue)
        assert not isinstance(issue, VerifierIssue)
        assert issue.error_type == "Compilation Error"


def test_clang_parse_error_line_26(clang_parse_error_output: ESBMCOutput) -> None:
    """Test that specific compilation error line is found."""
    # Find the issue for line 26
    line_26_issue = None
    for issue in clang_parse_error_output.issues:
        if issue.line_number == 26:
            line_26_issue = issue
            break

    assert line_26_issue is not None, "Expected to find compilation error at line 26"
    assert line_26_issue.error_type == "Compilation Error"


# =============================================================================
# Integration Tests - Full Workflow
# =============================================================================


def test_full_parsing_workflow_bubble_sort(bubble_sort_raw_output: str) -> None:
    """Test complete parsing workflow for bubble_sort sample."""
    # Parse output
    output = ESBMCOutputParser.parse_output(
        return_code=1,
        output=bubble_sort_raw_output,
    )

    # Verify basic properties
    assert not output.successful
    assert len(output.issues) == 1

    # Verify issue structure
    issue = output.issues[0]
    assert isinstance(issue, VerifierIssue)
    assert issue.error_type == "dereference failure: array bounds violated"
    assert issue.line_number == 7
    assert issue.function_name == "buggy_bubble_sort"

    # Verify stack trace
    assert len(issue.stack_trace) > 0
    assert issue.stack_trace[0].name == "main"
    assert issue.stack_trace[-1].name == "buggy_bubble_sort"

    # Verify counterexample
    assert len(issue.counterexample) > 0

    # Verify sections
    sections = output.sections
    assert sections.violated_property == "dereference failure: array bounds violated"
    assert sections.counterexample is not None
    assert sections.stack_trace is not None


def test_full_parsing_workflow_clang_error(clang_parse_error_raw_output: str) -> None:
    """Test complete parsing workflow for clang error sample."""
    # Parse output
    output = ESBMCOutputParser.parse_output(
        return_code=1,
        output=clang_parse_error_raw_output,
    )

    # Verify basic properties
    assert not output.successful
    assert len(output.issues) >= 1

    # Verify all issues are compilation errors
    for issue in output.issues:
        assert isinstance(issue, Issue)
        assert not isinstance(issue, VerifierIssue)
        assert issue.error_type == "Compilation Error"

    # Verify sections (should be empty for compilation errors)
    sections = output.sections
    assert sections.violated_property is None
    assert sections.counterexample is None
    assert sections.stack_trace is None


# =============================================================================
# Legacy Tests (maintained for compatibility)
# =============================================================================


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
    output = ESBMCOutputParser.parse_output(1, bubble_sort_output.output)
    assert output.sections.violated_property is not None

    # The violated property should contain the error message
    assert "dereference failure: array bounds violated" in output.sections.violated_property


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
