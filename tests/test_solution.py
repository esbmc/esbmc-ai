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
        solution = Solution(files=[file1, file2], base_dir=temp_path)

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
        solution = Solution(files=[test_file], base_dir=temp_path)
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
        solution = Solution(files=[file1, file2], base_dir=temp_path)
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
        solution = Solution(files=[file1, file2], base_dir=temp_path)
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
        source_file = SourceFile.load(test_file, temp_path)
        assert source_file.verify_file_integrity() is True


def test_verify_file_integrity_modified():
    """Test that verify_file_integrity returns False when content is modified."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.c"
        test_file.write_text("int main() { return 0; }")

        # Load from disk then modify content
        source_file = SourceFile.load(test_file, temp_path)
        source_file.content = "int main() { return 1; }"

        # Should be invalid - content doesn't match disk
        assert source_file.verify_file_integrity() is False


def test_verify_file_integrity_no_file():
    """Test that verify_file_integrity returns False when file doesn't exist."""
    # Create in-memory SourceFile without physical file
    source_file = SourceFile(
        file_path=Path("nonexistent.c"),
        base_path=Path("/tmp"),
        content="int main() { return 0; }",
    )

    # Should be invalid - file doesn't exist on disk
    assert source_file.verify_file_integrity() is False


def test_source_file_in_memory_creation():
    """Test that SourceFile can be created in-memory without physical files."""
    # This should not raise an error after Option C implementation
    source_file = SourceFile(
        file_path=Path("test.c"),
        base_path=Path("/tmp"),
        content="int main() { return 0; }",
    )

    # Should be created successfully
    assert source_file.content == "int main() { return 0; }"
    assert source_file.file_path == Path("test.c")
    assert source_file.base_path == Path("/tmp")


def test_source_file_repr_with_invalid_file():
    """Test that __repr__ correctly shows validity status for in-memory files."""
    # Create in-memory file (no physical file exists)
    source_file = SourceFile(
        file_path=Path("test.c"),
        base_path=Path("/tmp"),
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

        source_file = SourceFile.load(test_file, temp_path)
        repr_str = repr(source_file)

        assert "test.c" in repr_str
        assert "valid=True" in repr_str
