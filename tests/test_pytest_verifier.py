# Author: Yiannis Charalambous

import pytest
from pathlib import Path

from esbmc_ai.verifiers.pytest_verifier import PytestVerifierOutput


def load_test_data(filename: str) -> str:
    """Load test data from file."""
    path = Path(f"./tests/data/pytest_output/{filename}")
    with open(path, "r") as file:
        return file.read()


@pytest.fixture
def success_output() -> PytestVerifierOutput:
    """Fixture for successful pytest output."""
    output = load_test_data("success_output.txt")
    return PytestVerifierOutput(
        return_code=0,
        output=output,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        skipped_tests=0
    )


@pytest.fixture
def mixed_results_output() -> PytestVerifierOutput:
    """Fixture for mixed pytest results output."""
    output = load_test_data("mixed_results_output.txt")
    return PytestVerifierOutput(
        return_code=1,
        output=output,
        total_tests=10,
        passed_tests=6,
        failed_tests=3,
        skipped_tests=1
    )


@pytest.fixture
def failure_output() -> PytestVerifierOutput:
    """Fixture for pytest failure output."""
    output = load_test_data("failure_only_output.txt")
    return PytestVerifierOutput(
        return_code=1,
        output=output,
        total_tests=2,
        passed_tests=0,
        failed_tests=2,
        skipped_tests=0
    )


def test_pytest_successful_results(success_output):
    """Test pytest output parsing for successful tests."""
    output = success_output
    
    # Test basic properties
    assert output.successful()
    assert output.return_code == 0
    assert output.total_tests == 5
    assert output.passed_tests == 5
    assert output.failed_tests == 0
    assert output.skipped_tests == 0
    
    # Test calculated properties
    assert output.get_pass_rate() == 100.0
    assert output.get_failure_rate() == 0.0
    
    # Test issues
    issues = output.get_issues()
    assert len(issues) == 0
    
    # Test summary
    summary = output.get_test_summary()
    assert "5/5" in summary
    assert "100.0%" in summary


def test_pytest_mixed_results(mixed_results_output):
    """Test pytest output parsing for mixed results."""
    output = mixed_results_output
    
    # Test basic properties
    assert not output.successful()
    assert output.return_code == 1
    assert output.total_tests == 10
    assert output.passed_tests == 6
    assert output.failed_tests == 3
    assert output.skipped_tests == 1
    
    # Test calculated properties
    assert output.get_pass_rate() == 60.0
    assert output.get_failure_rate() == 30.0
    
    # Test issues
    issues = output.get_issues()
    assert len(issues) == 3  # Should have 3 failed tests
    
    for issue in issues:
        assert issue.severity == "error"
        assert issue.issue_type == "test_failure"
        assert "Test failed:" in issue.message
    
    # Test failed test names
    failed_names = output.get_failed_test_names()
    assert len(failed_names) == 3
    
    # Test summary
    summary = output.get_test_summary()
    assert "6/10" in summary
    assert "60.0%" in summary


def test_pytest_failure_results(failure_output):
    """Test pytest output parsing for all failed tests."""
    output = failure_output
    
    # Test basic properties
    assert not output.successful()
    assert output.return_code == 1
    assert output.total_tests == 2
    assert output.passed_tests == 0
    assert output.failed_tests == 2
    assert output.skipped_tests == 0
    
    # Test calculated properties
    assert output.get_pass_rate() == 0.0
    assert output.get_failure_rate() == 100.0
    
    # Test issues
    issues = output.get_issues()
    assert len(issues) == 2
    
    # Test stack trace extraction
    stack_trace = output.get_stack_trace()
    assert "FAILURES" in stack_trace
    assert len(stack_trace) > 0


def test_pytest_test_suite_verifier_methods(mixed_results_output):
    """Test TestSuiteVerifierOutput specific methods."""
    output = mixed_results_output
    
    # Test coverage info (should be empty by default)
    coverage = output.get_coverage_info()
    assert coverage == {}
    
    # Test test report
    report = output.get_test_report()
    assert "Test Results Summary:" in report
    assert "Total: 10" in report
    assert "Passed: 6" in report
    assert "Failed: 3" in report
    assert "Skipped: 1" in report
    assert "Pass Rate: 60.0%" in report
    assert "Failed Tests:" in report


def test_pytest_edge_cases():
    """Test edge cases for pytest output parsing."""
    # Test empty output
    empty_output = PytestVerifierOutput(
        return_code=0,
        output="",
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        skipped_tests=0
    )
    
    assert empty_output.successful()
    assert empty_output.get_pass_rate() == 0.0
    assert empty_output.get_failure_rate() == 0.0
    assert len(empty_output.get_issues()) == 0
    
    # Test with coverage data
    coverage_data = {
        "total_coverage": 85.5,
        "line_coverage": 90.0,
        "branch_coverage": 80.0
    }
    
    output_with_coverage = PytestVerifierOutput(
        return_code=0,
        output="Test output",
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        skipped_tests=0,
        coverage_data=coverage_data
    )
    
    assert output_with_coverage.get_coverage_info() == coverage_data


def test_pytest_primary_issue(mixed_results_output):
    """Test that primary issue works correctly for pytest output."""
    output = mixed_results_output
    
    primary_issue = output.get_primary_issue()
    assert primary_issue is not None
    assert primary_issue.severity == "error"
    assert primary_issue.issue_type == "test_failure"
    
    # Test legacy methods work through primary issue
    error_line = output.get_error_line()
    assert error_line == primary_issue.line_number
    
    error_line_idx = output.get_error_line_idx()
    assert error_line_idx == primary_issue.line_index