# Author: Yiannis Charalambous

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING
from pathlib import Path

from esbmc_ai.program_trace import ProgramTrace

# Avoid circular imports.
if TYPE_CHECKING:
    from esbmc_ai.solution import Solution


@dataclass
class VerificationIssue:
    """Represents a single verification issue."""
    
    file_path: Path
    """Path to the file where the issue occurred."""
    line_number: int
    """Line number where the issue occurred (1-indexed)."""
    issue_type: str
    """Type of issue (e.g., 'assertion_failure', 'null_pointer', 'test_failure')."""
    severity: str
    """Severity level: 'error', 'warning', 'info'."""
    message: str
    """Human-readable message describing the issue."""
    details: str | None = None
    """Additional details about the issue."""
    
    @property
    def line_index(self) -> int:
        """Returns the 0-indexed line number."""
        return self.line_number - 1


@dataclass
class VerifierOutput(ABC):
    """Class that represents the verifier output."""

    return_code: int
    """The return code of the verifier."""
    output: str
    """The output of the verifier."""

    @abstractmethod
    def successful(self) -> bool:
        """If the verification was successful."""
        raise NotImplementedError()

    @abstractmethod
    def get_issues(self) -> list[VerificationIssue]:
        """Returns all verification issues found."""
        raise NotImplementedError()

    def get_primary_issue(self) -> VerificationIssue | None:
        """Returns the most critical issue for legacy compatibility."""
        issues = self.get_issues()
        if not issues:
            return None
        
        # Return first error, or first warning if no errors
        errors = [i for i in issues if i.severity == "error"]
        return errors[0] if errors else issues[0]

    def get_error_line(self) -> int:
        """Returns the line number of where the primary error occurred."""
        issue = self.get_primary_issue()
        if issue is None:
            raise ValueError("No primary issue available")
        return issue.line_number

    def get_error_line_idx(self) -> int:
        """Returns the line index of where the primary error occurred."""
        issue = self.get_primary_issue()
        if issue is None:
            raise ValueError("No primary issue available")
        return issue.line_index

    def get_error_type(self) -> str:
        """Returns a string of the type of primary error found by the verifier output."""
        issue = self.get_primary_issue()
        if issue is None:
            raise ValueError("No primary issue available")
        return issue.issue_type

    @abstractmethod
    def get_stack_trace(self) -> str:
        """Gets the stack trace that points to the error."""
        raise NotImplementedError()

    @abstractmethod
    def get_trace(
        self,
        solution: "Solution",
        load_libs=False,
    ) -> list[ProgramTrace]:
        """Returns a more detailed trace. Each line that causes the error is
        returned. Given a counterexample."""
        _ = solution
        _ = load_libs
        raise NotImplementedError()


@dataclass  
class FormalVerifierOutput(VerifierOutput):
    """Specialized output class for formal verification tools like ESBMC."""
    
    def get_counterexample(self) -> str | None:
        """Returns counterexample if available for formal verifiers."""
        primary_issue = self.get_primary_issue()
        return primary_issue.details if primary_issue else None
    
    def get_violated_property(self) -> str | None:
        """Returns the violated property description if available."""
        return None  # Default implementation, override in subclasses
    
    def get_program_trace(self) -> str | None:
        """Returns program execution trace leading to violation."""
        return None  # Default implementation, override in subclasses


@dataclass
class TestSuiteVerifierOutput(VerifierOutput):
    """Specialized output class for test suite verifiers like pytest."""
    
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    
    def get_pass_rate(self) -> float:
        """Returns the pass rate as a percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100.0
    
    def get_failure_rate(self) -> float:
        """Returns the failure rate as a percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.failed_tests / self.total_tests) * 100.0
    
    def get_test_summary(self) -> str:
        """Returns a summary of test results."""
        return f"{self.passed_tests}/{self.total_tests} tests passed ({self.get_pass_rate():.1f}%)"
    
    def get_failed_test_names(self) -> list[str]:
        """Returns names of failed tests."""
        failed_issues = [issue for issue in self.get_issues() if issue.severity == "error"]
        return [issue.message for issue in failed_issues]
        
    @abstractmethod
    def get_coverage_info(self) -> dict | None:
        """Returns test coverage information if available."""
        raise NotImplementedError()
