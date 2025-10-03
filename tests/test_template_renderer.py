# Author: Yiannis Charalambous

from esbmc_ai.chats.template_renderer import KeyTemplateRenderer
from esbmc_ai.chats.template_key_provider import ESBMCTemplateKeyProvider


def test_template_substitution():
    """Test that template variables are correctly substituted."""
    template_str = "The ESBMC output is:\n\n```\n{esbmc_output}\n```\n\nThe source code is:\n\n```c\n{source_code}\n```"
    messages = [("human", template_str)]

    renderer = KeyTemplateRenderer(
        messages=messages,
        key_provider=ESBMCTemplateKeyProvider(),
    )

    formatted = renderer.format_messages(
        source_code="int main() { return 0; }",
        esbmc_output="VERIFICATION SUCCESSFUL",
        error_line="0",
        error_type="none",
    )

    assert len(formatted) == 1
    assert "int main() { return 0; }" in formatted[0].content
    assert "VERIFICATION SUCCESSFUL" in formatted[0].content
    assert "{source_code}" not in formatted[0].content
    assert "{esbmc_output}" not in formatted[0].content


def test_template_substitution_with_multiline_code():
    """Test template substitution with multiline source code."""
    template_str = "Source:\n{source_code}\nError: {error_type}"
    messages = [("human", template_str)]

    renderer = KeyTemplateRenderer(
        messages=messages,
        key_provider=ESBMCTemplateKeyProvider(),
    )

    source = """int main() {
    int x = 5;
    return x / 0;
}"""

    formatted = renderer.format_messages(
        source_code=source,
        esbmc_output="Division by zero",
        error_line="3",
        error_type="division by zero",
    )

    assert len(formatted) == 1
    assert "int x = 5;" in formatted[0].content
    assert "return x / 0;" in formatted[0].content
    assert "division by zero" in formatted[0].content
