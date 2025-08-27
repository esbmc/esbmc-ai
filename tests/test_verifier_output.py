# Author: Yiannis Charalambous

import pytest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

from esbmc_ai.verifier_output import (
    VerificationIssue,
    VerifierOutput, 
    FormalVerifierOutput,
    TestSuiteVerifierOutput
)
from esbmc_ai.program_trace import ProgramTrace


class MockVerifierOutput(VerifierOutput):
    """Mock implementation for testing base VerifierOutput."""
    
    def __init__(self, return_code: int, output: str, issues: list[VerificationIssue] = None):
        super().__init__(return_code=return_code, output=output)
        self._issues = issues or []
    
    def successful(self) -> bool:
        return self.return_code == 0 and len(self._issues) == 0
    
    def get_issues(self) -> list[VerificationIssue]:
        return self._issues
    
    def get_stack_trace(self) -> str:
        return "Mock stack trace"
    
    def get_trace(self, solution, load_libs=False) -> list[ProgramTrace]:
        return []


class MockFormalVerifierOutput(FormalVerifierOutput):
    """Mock implementation for testing FormalVerifierOutput."""
    
    def __init__(self, return_code: int, output: str, issues: list[VerificationIssue] = None):
        super().__init__(return_code=return_code, output=output)
        self._issues = issues or []
    
    def successful(self) -> bool:
        return self.return_code == 0 and len(self._issues) == 0
    
    def get_issues(self) -> list[VerificationIssue]:
        return self._issues
    
    def get_stack_trace(self) -> str:
        return "Formal verifier stack trace"
    
    def get_trace(self, solution, load_libs=False) -> list[ProgramTrace]:
        return []
    
    def get_violated_property(self) -> str | None:
        return "assertion failure" if self._issues else None


class MockTestSuiteVerifierOutput(TestSuiteVerifierOutput):
    """Mock implementation for testing TestSuiteVerifierOutput."""
    
    def __init__(
        self, 
        return_code: int, 
        output: str, 
        total_tests: int = 0,
        passed_tests: int = 0,
        failed_tests: int = 0,
        skipped_tests: int = 0,
        issues: list[VerificationIssue] = None
    ):
        super().__init__(
            return_code=return_code,
            output=output,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests
        )
        self._issues = issues or []
    
    def successful(self) -> bool:
        return self.return_code == 0 and self.failed_tests == 0
    
    def get_issues(self) -> list[VerificationIssue]:
        return self._issues
    
    def get_stack_trace(self) -> str:
        return "Test suite stack trace"
    
    def get_trace(self, solution, load_libs=False) -> list[ProgramTrace]:
        return []
    
    def get_coverage_info(self) -> dict | None:
        return {"line_coverage": 85.0, "branch_coverage": 78.5}


def test_verification_issue_creation():
    """Test VerificationIssue dataclass functionality."""
    issue = VerificationIssue(
        file_path=Path("test.c"),
        line_number=10,
        issue_type="assertion_failure",
        severity="error",
        message="Assertion failed",
        details="Additional details"
    )
    
    assert issue.file_path == Path("test.c")
    assert issue.line_number == 10
    assert issue.line_index == 9  # 0-indexed
    assert issue.issue_type == "assertion_failure"
    assert issue.severity == "error"
    assert issue.message == "Assertion failed"
    assert issue.details == "Additional details"


def test_base_verifier_output():
    """Test base VerifierOutput functionality."""
    # Create test issues
    issues = [
        VerificationIssue(
            file_path=Path("test.c"),
            line_number=5,
            issue_type="warning", 
            severity="warning",
            message="Warning message"
        ),
        VerificationIssue(
            file_path=Path("test.c"),
            line_number=10,
            issue_type="error",
            severity="error", 
            message="Error message"
        )
    ]
    
    output = MockVerifierOutput(return_code=1, output="test output", issues=issues)
    
    # Test basic properties
    assert output.return_code == 1
    assert output.output == "test output"
    assert not output.successful()
    
    # Test issue handling
    all_issues = output.get_issues()
    assert len(all_issues) == 2
    
    # Test primary issue (should return first error)
    primary = output.get_primary_issue()
    assert primary is not None
    assert primary.severity == "error"
    assert primary.line_number == 10
    
    # Test legacy methods
    assert output.get_error_line() == 10
    assert output.get_error_line_idx() == 9
    assert output.get_error_type() == "error"


def test_base_verifier_output_no_issues():
    """Test base VerifierOutput with no issues."""
    output = MockVerifierOutput(return_code=0, output="success")
    
    assert output.successful()
    assert len(output.get_issues()) == 0
    assert output.get_primary_issue() is None
    
    # Test legacy methods raise appropriate errors
    with pytest.raises(ValueError, match="No primary issue available"):
        output.get_error_line()
    
    with pytest.raises(ValueError, match="No primary issue available"):
        output.get_error_line_idx()
    
    with pytest.raises(ValueError, match="No primary issue available"):
        output.get_error_type()


def test_base_verifier_output_warnings_only():
    """Test primary issue selection when only warnings exist."""
    issues = [
        VerificationIssue(
            file_path=Path("test.c"),
            line_number=5,
            issue_type="warning",
            severity="warning",
            message="Warning 1"
        ),
        VerificationIssue(
            file_path=Path("test.c"),
            line_number=8,
            issue_type="warning", 
            severity="warning",
            message="Warning 2"
        )
    ]
    
    output = MockVerifierOutput(return_code=1, output="warnings", issues=issues)
    
    # Should return first warning as primary issue
    primary = output.get_primary_issue()
    assert primary is not None
    assert primary.severity == "warning"
    assert primary.line_number == 5


def test_formal_verifier_output():
    """Test FormalVerifierOutput specialized functionality."""
    issues = [
        VerificationIssue(
            file_path=Path("test.c"),
            line_number=15,
            issue_type="assertion_failure",
            severity="error",
            message="Assertion failed",
            details="Counterexample details"
        )
    ]
    
    output = MockFormalVerifierOutput(return_code=1, output="formal output", issues=issues)
    
    # Test specialized methods
    assert output.get_counterexample() == "Counterexample details"
    assert output.get_violated_property() == "assertion failure"
    assert output.get_program_trace() is None  # Default implementation
    
    # Test inheritance
    assert isinstance(output, VerifierOutput)
    assert not output.successful()


def test_test_suite_verifier_output():
    """Test TestSuiteVerifierOutput specialized functionality."""
    issues = [
        VerificationIssue(
            file_path=Path("test_file.py"),
            line_number=20,
            issue_type="test_failure",
            severity="error",
            message="Test failed: test_function"
        )
    ]
    
    output = MockTestSuiteVerifierOutput(
        return_code=1,
        output="test output",
        total_tests=10,
        passed_tests=8,
        failed_tests=2,
        skipped_tests=0,
        issues=issues
    )
    
    # Test basic test statistics
    assert output.total_tests == 10
    assert output.passed_tests == 8
    assert output.failed_tests == 2
    assert output.skipped_tests == 0
    
    # Test calculated rates
    assert output.get_pass_rate() == 80.0
    assert output.get_failure_rate() == 20.0
    
    # Test summary
    summary = output.get_test_summary()
    assert "8/10" in summary
    assert "80.0%" in summary
    
    # Test failed test names
    failed_names = output.get_failed_test_names()
    assert len(failed_names) == 1
    assert "Test failed: test_function" in failed_names
    
    # Test coverage info
    coverage = output.get_coverage_info()
    assert coverage["line_coverage"] == 85.0
    assert coverage["branch_coverage"] == 78.5
    
    # Test inheritance
    assert isinstance(output, VerifierOutput)
    assert not output.successful()


def test_test_suite_verifier_output_edge_cases():
    """Test TestSuiteVerifierOutput edge cases."""
    # Test with zero tests
    output = MockTestSuiteVerifierOutput(
        return_code=0,
        output="no tests",
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        skipped_tests=0
    )
    
    assert output.get_pass_rate() == 0.0
    assert output.get_failure_rate() == 0.0
    assert output.successful()
    
    # Test with all tests passing
    output_success = MockTestSuiteVerifierOutput(
        return_code=0,
        output="all passed",
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        skipped_tests=0
    )
    
    assert output_success.get_pass_rate() == 100.0
    assert output_success.get_failure_rate() == 0.0
    assert output_success.successful()


def test_inheritance_hierarchy():
    """Test that the class hierarchy is set up correctly."""
    # Test FormalVerifierOutput inheritance
    formal_output = MockFormalVerifierOutput(return_code=0, output="formal")
    assert isinstance(formal_output, VerifierOutput)
    assert isinstance(formal_output, FormalVerifierOutput)
    
    # Test TestSuiteVerifierOutput inheritance  
    test_output = MockTestSuiteVerifierOutput(return_code=0, output="test")
    assert isinstance(test_output, VerifierOutput)
    assert isinstance(test_output, TestSuiteVerifierOutput)
    
    # Test that they're different types
    assert not isinstance(formal_output, TestSuiteVerifierOutput)
    assert not isinstance(test_output, FormalVerifierOutput)


def test_abstract_methods_enforcement():
    """Test that abstract methods are properly enforced."""
    # Cannot instantiate abstract base classes
    with pytest.raises(TypeError):
        VerifierOutput(return_code=0, output="test")
    
    with pytest.raises(TypeError):
        FormalVerifierOutput(return_code=0, output="test")
    
    with pytest.raises(TypeError):
        TestSuiteVerifierOutput(return_code=0, output="test")