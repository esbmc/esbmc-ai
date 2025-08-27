# Author: Yiannis Charalambous

"""Pytest verifier implementation for test suite verification."""

import re
import json
from pathlib import Path
from typing import Any, override
from subprocess import run, PIPE, STDOUT, CompletedProcess

from esbmc_ai.solution import Solution
from esbmc_ai.verifier_output import TestSuiteVerifierOutput, VerificationIssue
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.program_trace import ProgramTrace


class PytestVerifierOutput(TestSuiteVerifierOutput):
    """Pytest-specific verifier output that extends TestSuiteVerifierOutput."""
    
    def __init__(
        self, 
        return_code: int, 
        output: str,
        total_tests: int = 0,
        passed_tests: int = 0,
        failed_tests: int = 0, 
        skipped_tests: int = 0,
        coverage_data: dict | None = None
    ):
        super().__init__(
            return_code=return_code,
            output=output,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests
        )
        self._coverage_data = coverage_data or {}
    
    @override
    def successful(self) -> bool:
        """Tests are successful if all passed and none failed."""
        return self.return_code == 0 and self.failed_tests == 0
    
    @override
    def get_issues(self) -> list[VerificationIssue]:
        """Parse pytest output to extract test failures as verification issues."""
        issues = []
        if self.successful():
            return issues
            
        # Parse pytest output for failures - look for lines with FAILED
        failure_pattern = r"(.+?) FAILED"
        matches = re.findall(failure_pattern, self.output)
        
        for match in matches:
            test_name = match.strip()
            
            # Try to extract line number from test name (default to 1)
            line_number = 1
            
            # Look for corresponding error details in FAILURES section
            error_details = self._extract_failure_details(test_name)
            
            issue = VerificationIssue(
                file_path=Path(test_name.split("::")[0] if "::" in test_name else "test_file"),
                line_number=line_number,
                issue_type="test_failure",
                severity="error",
                message=f"Test failed: {test_name}",
                details=error_details
            )
            issues.append(issue)
        
        return issues
    
    def _extract_failure_details(self, test_name: str) -> str:
        """Extract failure details for a specific test from the FAILURES section."""
        # Look for the test name in the failures section
        failure_start = self.output.find(f"____________________________ {test_name.split('::')[-1]} ____________________________")
        if failure_start == -1:
            return "Test failed"
        
        # Find the end of this failure section (next test or end of failures)
        next_test_start = self.output.find("____________________________", failure_start + 1)
        if next_test_start == -1:
            next_test_start = self.output.find("=", failure_start + 100)  # Find next section
        
        if next_test_start == -1:
            failure_section = self.output[failure_start:]
        else:
            failure_section = self.output[failure_start:next_test_start]
        
        # Extract the error message (usually after "E   ")
        error_lines = []
        for line in failure_section.split('\n'):
            if line.startswith('E   '):
                error_lines.append(line[4:])  # Remove "E   " prefix
        
        return '\n'.join(error_lines) if error_lines else "Test failed"
    
    @override
    def get_stack_trace(self) -> str:
        """Extract stack trace from pytest output."""
        # Look for traceback sections in pytest output
        traceback_start = self.output.find("FAILURES")
        if traceback_start == -1:
            return ""
        
        traceback_end = self.output.find("=", traceback_start + 8)  # Find next section
        if traceback_end == -1:
            traceback_end = len(self.output)
        
        return self.output[traceback_start:traceback_end]
    
    @override
    def get_trace(
        self, 
        solution: "Solution", 
        load_libs: bool = False
    ) -> list[ProgramTrace]:
        """Extract program traces from test failures."""
        traces = []
        
        # For pytest, we extract information about failed tests
        for idx, issue in enumerate(self.get_issues()):
            trace = ProgramTrace(
                trace_source="pytest",
                trace_index=idx,
                source_file=solution.files_mapped.get(str(issue.file_path)),
                line_idx=issue.line_number,
                name=issue.message,
                comment=issue.details
            )
            traces.append(trace)
        
        return traces
    
    @override 
    def get_coverage_info(self) -> dict | None:
        """Return coverage information if available."""
        return self._coverage_data
    
    def get_test_report(self) -> str:
        """Return a formatted test report."""
        report = f"Test Results Summary:\n"
        report += f"  Total: {self.total_tests}\n"
        report += f"  Passed: {self.passed_tests}\n"
        report += f"  Failed: {self.failed_tests}\n"
        report += f"  Skipped: {self.skipped_tests}\n"
        report += f"  Pass Rate: {self.get_pass_rate():.1f}%\n"
        
        if self.failed_tests > 0:
            report += f"\nFailed Tests:\n"
            for test_name in self.get_failed_test_names():
                report += f"  - {test_name}\n"
        
        return report


class PytestVerifier(BaseSourceVerifier):
    """Verifier class that uses pytest for test execution."""
    
    def __init__(self) -> None:
        super().__init__(verifier_name="pytest", authors="ESBMC-AI Team")
    
    @override
    def verify_source(
        self,
        *,
        solution: Solution,
        timeout: int | None = None,
        test_path: str = "tests/",
        params: list[str] | None = None,
        **kwargs: Any
    ) -> PytestVerifierOutput:
        """Run pytest on the solution and return results."""
        _ = kwargs
        
        pytest_params = params if params else ["--tb=short", "-v"]
        
        # Build pytest command
        pytest_cmd = ["python", "-m", "pytest"]
        pytest_cmd.extend(pytest_params)
        
        # Add test path
        test_dir = solution.base_dir / test_path
        if test_dir.exists():
            pytest_cmd.append(str(test_dir))
        else:
            pytest_cmd.append(str(solution.base_dir))
        
        self._logger.info("Running pytest: " + " ".join(pytest_cmd))
        
        # Run pytest
        process: CompletedProcess = run(
            pytest_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=solution.base_dir,
            timeout=timeout,
            check=False,
        )
        
        output = process.stdout.decode("utf-8")
        
        # Parse pytest output for test counts
        total_tests, passed_tests, failed_tests, skipped_tests = self._parse_test_counts(output)
        
        return PytestVerifierOutput(
            return_code=process.returncode,
            output=output,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests
        )
    
    def _parse_test_counts(self, output: str) -> tuple[int, int, int, int]:
        """Parse pytest output to extract test counts."""
        # Look for the summary line like "1 failed, 2 passed, 1 skipped"
        summary_pattern = r"(\d+) failed.*?(\d+) passed.*?(\d+) skipped"
        match = re.search(summary_pattern, output)
        
        if match:
            failed = int(match.group(1))
            passed = int(match.group(2))
            skipped = int(match.group(3))
            total = failed + passed + skipped
            return total, passed, failed, skipped
        
        # Fallback: try simpler patterns
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        skipped_match = re.search(r"(\d+) skipped", output)
        
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        total = passed + failed + skipped
        
        return total, passed, failed, skipped