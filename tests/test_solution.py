# Author: Yiannis Charalambous

from pathlib import Path
from tempfile import TemporaryDirectory

from esbmc_ai.solution import SourceFile, Solution, SolutionIntegrityError

#####################################
# Solution
#####################################


def test_verify_solution_integrity_all_valid():
    """Test that verify_solution_integrity returns True when all files match disk."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.c"
        file1.write_text("int main() { return 0; }")
        file2 = temp_path / "test2.c"
        file2.write_text("void foo() {}")

        # Create solution from files
        solution = Solution(files=[file1, file2])

        # Should be valid - all files match disk
        assert solution.verify_solution_integrity() is True


def test_verify_solution_integrity_modified_file():
    """Test that verify_solution_integrity returns False when a file is modified in memory."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test file
        test_file = temp_path / "test.c"
        test_file.write_text("int main() { return 0; }")

        # Create solution and modify content in memory
        solution = Solution(files=[test_file])
        solution.files[0].content = "int main() { return 1; }"

        # Should be invalid - content doesn't match disk
        assert solution.verify_solution_integrity() is False


def test_verify_solution_integrity_mixed():
    """Test verify_solution_integrity with some valid and some invalid files."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.c"
        file1.write_text("int main() { return 0; }")
        file2 = temp_path / "test2.c"
        file2.write_text("void foo() {}")

        # Create solution and modify one file
        solution = Solution(files=[file1, file2])
        solution.files[1].content = "void foo() { modified }"

        # Should be invalid - one file doesn't match
        assert solution.verify_solution_integrity() is False


def test_solution_integrity_error():
    """Test that SolutionIntegrityError is raised with correct information."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.c"
        file1.write_text("int main() { return 0; }")
        file2 = temp_path / "test2.c"
        file2.write_text("void foo() {}")

        # Create solution and modify files
        solution = Solution(files=[file1, file2])
        solution.files[0].content = "modified1"
        solution.files[1].content = "modified2"

        # Create integrity error
        error = SolutionIntegrityError(solution.files)

        # Check that all modified files are listed
        assert len(error.invalid_files) == 2
        assert all(not f.verify_file_integrity() for f in error.invalid_files)
        assert "test1.c" in str(error)
        assert "test2.c" in str(error)


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


def test_verify_file_integrity_valid():
    """Test that verify_file_integrity returns True when content matches disk."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.c"
        test_file.write_text("int main() { return 0; }")

        # Load from disk - should be valid
        source_file = SourceFile.load(test_file)
        assert source_file.verify_file_integrity() is True


def test_verify_file_integrity_modified():
    """Test that verify_file_integrity returns False when content is modified."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.c"
        test_file.write_text("int main() { return 0; }")

        # Load from disk then modify content
        source_file = SourceFile.load(test_file)
        source_file.content = "int main() { return 1; }"

        # Should be invalid - content doesn't match disk
        assert source_file.verify_file_integrity() is False


def test_verify_file_integrity_no_file():
    """Test that verify_file_integrity returns False when file doesn't exist."""
    # Create in-memory SourceFile without physical file
    source_file = SourceFile(
        file_path=Path("/tmp/nonexistent.c"),
        content="int main() { return 0; }",
    )

    # Should be invalid - file doesn't exist on disk
    assert source_file.verify_file_integrity() is False


def test_source_file_in_memory_creation():
    """Test that SourceFile can be created in-memory without physical files."""
    # SourceFile now uses absolute paths
    source_file = SourceFile(
        file_path=Path("/tmp/test.c"),
        content="int main() { return 0; }",
    )

    # Should be created successfully
    assert source_file.content == "int main() { return 0; }"
    assert source_file.file_path == Path("/tmp/test.c")


def test_source_file_repr_with_invalid_file():
    """Test that __repr__ correctly shows validity status for in-memory files."""
    # Create in-memory file (no physical file exists)
    source_file = SourceFile(
        file_path=Path("/tmp/test.c"),
        content="int main() { return 0; }",
    )

    repr_str = repr(source_file)
    assert "test.c" in repr_str
    assert "valid=False" in repr_str  # File doesn't exist on disk


def test_source_file_repr_with_valid_file():
    """Test that __repr__ correctly shows validity status for files matching disk."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.c"
        test_file.write_text("int main() { return 0; }")

        source_file = SourceFile.load(test_file)
        repr_str = repr(source_file)

        assert "test.c" in repr_str
        assert "valid=True" in repr_str


def test_solution_add_operator_preserves_structure():
    """
    Test that __add__ operator combines solutions while preserving file
    structure.
    """
    # Use the test-add-solution sample
    sample_dir = Path(__file__).parent / "samples" / "solutions" / "test-add-solution"

    # Load main solution (main.c, src/)
    main_solution = Solution.from_paths(
        sample_dir / "main.c",
        sample_dir / "src",
    )

    # Load harness solution (harness/)
    harness_solution = Solution.from_paths(
        sample_dir / "harness",
    )

    # Verify working_dir before merge
    assert (
        main_solution.working_dir == sample_dir
    ), f"Main solution working_dir should be {sample_dir}"
    assert (
        harness_solution.working_dir == sample_dir / "harness"
    ), f"Harness solution working_dir should be {sample_dir / 'harness'}"

    # Combine solutions - this should merge in-memory without saving
    combined = main_solution + harness_solution

    # Assert: Files should retain their original paths (not relocated)
    assert all(
        str(f.file_path).startswith(str(sample_dir)) for f in combined.files
    ), "Combined solution files should retain their original paths"

    # Assert: working_dir should be the common parent (sample_dir)
    # When merging solutions with different working_dirs, the combined solution's
    # working_dir becomes the common ancestor of all files
    assert (
        combined.working_dir == sample_dir
    ), f"Combined working_dir should be {sample_dir}, got: {combined.working_dir}"
    assert (
        combined.working_dir == main_solution.working_dir
    ), "Combined working_dir should match main_solution (not harness)"
    assert (
        combined.working_dir != harness_solution.working_dir
    ), "Combined working_dir should differ from harness (moved up to common parent)"

    # Assert: All files from both solutions are present
    assert len(combined.files) == len(main_solution.files) + len(
        harness_solution.files
    ), "Combined should have all files from both solutions"
    assert len(combined.files) == 4, f"Should have 4 files total"
