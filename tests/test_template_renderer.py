# Author: Yiannis Charalambous

from pathlib import Path

from esbmc_ai.chats import KeyTemplateRenderer, OracleTemplateKeyProvider
from esbmc_ai.solution import Solution, SourceFile


def test_template_substitution():
    """Test that template variables are correctly substituted."""
    template_str = "The oracle output is:\n\n```\n{{oracle_output}}\n```\n\nThe source code is:\n\n```c\n{{solution.files[0].content}}\n```"
    messages = [("human", template_str)]

    renderer = KeyTemplateRenderer(
        messages=messages,
        key_provider=OracleTemplateKeyProvider(),
    )

    source_file = SourceFile(
        file_path=Path("/tmp/test.c"),
        content="int main() { return 0; }",
    )
    solution = Solution()
    solution.add_source_file(source_file)

    formatted = renderer.format_messages(
        solution=solution,
        oracle_output="VERIFICATION SUCCESSFUL",
        error_line="0",
        error_type="none",
    )

    assert len(formatted) == 1
    assert "int main() { return 0; }" in formatted[0].content
    assert "VERIFICATION SUCCESSFUL" in formatted[0].content
    assert "{{solution.files[0].content}}" not in formatted[0].content
    assert "{{oracle_output}}" not in formatted[0].content


def test_template_substitution_with_multiline_code():
    """Test template substitution with multiline source code."""
    template_str = "Source:\n{{solution.files[0].content}}\nError: {{error_type}}"
    messages = [("human", template_str)]

    renderer = KeyTemplateRenderer(
        messages=messages,
        key_provider=OracleTemplateKeyProvider(),
    )

    source = """int main() {
    int x = 5;
    return x / 0;
}"""

    source_file = SourceFile(
        file_path=Path("/tmp/test.c"),
        content=source,
    )
    solution = Solution()
    solution.add_source_file(source_file)

    formatted = renderer.format_messages(
        solution=solution,
        oracle_output="Division by zero",
        error_line="3",
        error_type="division by zero",
    )

    assert len(formatted) == 1
    assert "int x = 5;" in formatted[0].content
    assert "return x / 0;" in formatted[0].content
    assert "division by zero" in formatted[0].content
