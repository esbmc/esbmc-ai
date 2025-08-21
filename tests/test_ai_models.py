# Author: Yiannis Charalambous

from dataclasses import dataclass, field
from typing import override
from langchain.prompts.chat import ChatPromptValue
from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    PromptValue,
    SystemMessage,
)
from langchain_core.language_models import BaseChatModel, FakeListChatModel
from pytest import raises
import pytest

from esbmc_ai.ai_models import (
    AIModel,
    AIModelOpenAI,
    AIModels,
)


@dataclass(frozen=True, kw_only=True)
class MockAIModel(AIModel):
    """Used to test AIModels, it implements some mock versions of abstract
    methods."""

    responses: list[str] = field(default_factory=list[str])

    @override
    def create_llm(self) -> BaseChatModel:
        return FakeListChatModel(responses=self.responses)

    @override
    def get_num_tokens(self, content: str) -> int:
        _ = content
        return len(content)

    @override
    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        _ = messages
        return sum(len(str(msg.content)) for msg in messages)


@pytest.fixture(autouse=True)
def clear_ai_models():
    """Clear the AIModels singleton state before each test."""
    # Clear the singleton's internal state
    AIModels()._ai_models.clear()
    yield
    # Optionally clear after test as well
    AIModels()._ai_models.clear()


def test_is_not_valid_ai_model() -> None:
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )
    assert not AIModels().is_valid_ai_model(custom_model)
    assert not AIModels().is_valid_ai_model("doesn't exist")


def test_add_custom_ai_model() -> None:
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )

    AIModels().add_ai_model(custom_model)

    assert AIModels().is_valid_ai_model(custom_model.name)

    # Test add again.

    if AIModels().is_valid_ai_model(custom_model.name):
        with raises(Exception):
            AIModels().add_ai_model(custom_model)

    assert AIModels().is_valid_ai_model(custom_model.name)


def test_get_ai_model_by_name() -> None:
    # Try with first class AI
    # assert get_ai_model_by_name("falcon-7b")

    # Try with custom AI.
    # Add custom AI model if not added by previous tests.
    custom_model: MockAIModel = MockAIModel(
        name="custom_ai",
        tokens=999,
    )
    if not AIModels().is_valid_ai_model(custom_model.name):
        AIModels().add_ai_model(custom_model)
    assert AIModels().get_ai_model("custom_ai") is not None

    # Try with non existent.
    with raises(Exception):
        AIModels().get_ai_model("not-exists")


def test_apply_chat_template() -> None:
    messages: list = [
        SystemMessage(content="M1"),
        HumanMessage(content="M2"),
        AIMessage(content="M3"),
    ]

    # Test the identity method.
    custom_model_1: MockAIModel = MockAIModel(
        name="custom",
        tokens=999,
    )

    prompt: PromptValue = custom_model_1.apply_chat_template(messages=messages)

    assert prompt == ChatPromptValue(messages=messages)


def test_safe_substitute() -> None:
    """Tests that safe template substitution works correctly."""
    
    # Test basic substitution
    result = MockAIModel.safe_substitute("Hello $name, you have $count messages", name="Alice", count=5)
    assert result == "Hello Alice, you have 5 messages"
    
    # Test missing variables are left unchanged
    result = MockAIModel.safe_substitute("Hello $name, you have $count messages", name="Alice")
    assert result == "Hello Alice, you have $count messages"
    
    # Test no variables
    result = MockAIModel.safe_substitute("Hello world")
    assert result == "Hello world"
    
    # Test mixed defined and undefined
    result = MockAIModel.safe_substitute("Process $input with $method using $tool", input="data.txt", tool="hammer")
    assert result == "Process data.txt with $method using hammer"


def test_safe_substitute_special_characters() -> None:
    """Test substitution with special characters and escaping."""
    
    # Test literal dollar signs (double dollar becomes single)
    result = MockAIModel.safe_substitute("Price is $$50", price=100)
    assert result == "Price is $50"
    
    # Test variables with underscores and numbers
    result = MockAIModel.safe_substitute("File: $file_name_2", file_name_2="test.txt")
    assert result == "File: test.txt"
    
    # Test variables at string boundaries
    result = MockAIModel.safe_substitute("$start middle $end", start="BEGIN", end="FINISH")
    assert result == "BEGIN middle FINISH"


def test_safe_substitute_data_types() -> None:
    """Test substitution with different data types."""
    
    # Test with None values
    result = MockAIModel.safe_substitute("Value: $value", value=None)
    assert result == "Value: None"
    
    # Test with boolean values
    result = MockAIModel.safe_substitute("Enabled: $enabled, Debug: $debug", enabled=True, debug=False)
    assert result == "Enabled: True, Debug: False"
    
    # Test with numeric values
    result = MockAIModel.safe_substitute("Count: $count, Rate: $rate", count=0, rate=3.14)
    assert result == "Count: 0, Rate: 3.14"
    
    # Test with list and dict (stringify behavior)
    result = MockAIModel.safe_substitute("List: $items, Dict: $config", items=[1, 2, 3], config={"key": "value"})
    assert result == "List: [1, 2, 3], Dict: {'key': 'value'}"


def test_safe_substitute_whitespace_formatting() -> None:
    """Test substitution with whitespace and formatting edge cases."""
    
    # Test multiline strings
    multiline = """Line 1: $var1
Line 2: $var2
Line 3: $undefined"""
    result = MockAIModel.safe_substitute(multiline, var1="value1", var2="value2")
    expected = """Line 1: value1
Line 2: value2
Line 3: $undefined"""
    assert result == expected
    
    # Test with tabs and spaces
    result = MockAIModel.safe_substitute("\t$var\n  $other  ", var="tabbed", other="spaced")
    assert result == "\ttabbed\n  spaced  "


def test_safe_substitute_consecutive_variables() -> None:
    """Test substitution with consecutive variables."""
    
    # Test consecutive variables without separators
    result = MockAIModel.safe_substitute("$prefix$suffix$extension", prefix="file", suffix="name", extension=".txt")
    assert result == "filename.txt"
    
    # Test multiple undefined consecutive variables
    result = MockAIModel.safe_substitute("$a$b$c$d", a="A", c="C")
    assert result == "A$bC$d"


def test_safe_substitute_boundary_conditions() -> None:
    """Test boundary conditions for substitution."""
    
    # Test empty string
    result = MockAIModel.safe_substitute("", var="value")
    assert result == ""
    
    # Test string with only variable
    result = MockAIModel.safe_substitute("$only", only="result")
    assert result == "result"
    
    # Test undefined variable only
    result = MockAIModel.safe_substitute("$undefined")
    assert result == "$undefined"


def test_safe_substitute_invalid_variable_patterns() -> None:
    """Test handling of invalid or malformed variable patterns."""
    
    # Test variables starting with numbers (invalid Python identifiers)
    result = MockAIModel.safe_substitute("Value: $1var $2test", var="valid")
    assert result == "Value: $1var $2test"  # Should remain unchanged as invalid identifiers
    
    # Test variables with hyphens - Template treats "var" as the variable name and stops at hyphen
    result = MockAIModel.safe_substitute("Config: $var-name $test-value", var="valid")
    assert result == "Config: valid-name $test-value"  # "var" gets substituted, hyphen treated as separator
    
    # Test lone dollar sign
    result = MockAIModel.safe_substitute("Price: $ and $valid", valid="100")
    assert result == "Price: $ and 100"


def test_safe_substitute_recursive_values() -> None:
    """Test substitution where values contain variable-like patterns."""
    
    # Test when substitution values contain dollar signs
    result = MockAIModel.safe_substitute("Template: $template_content", template_content="Use $variable for substitution")
    assert result == "Template: Use $variable for substitution"
    
    # Test when values look like variables but shouldn't be re-substituted
    result = MockAIModel.safe_substitute("$msg", msg="Hello $world")
    assert result == "Hello $world"  # Should not recursively substitute $world


def test_safe_substitute_unicode() -> None:
    """Test substitution with Unicode characters."""
    
    # Test Unicode in content and values
    result = MockAIModel.safe_substitute("Greeting: $greeting", greeting="Hello 世界!")
    assert result == "Greeting: Hello 世界!"
    
    # Test Unicode variable names - Python's Template class doesn't support Unicode identifiers
    # So Unicode variable names remain unchanged
    result = MockAIModel.safe_substitute("文档: $文档", **{"文档": "document.txt"})
    assert result == "文档: $文档"


def test__get_openai_model_max_tokens() -> None:
    assert AIModelOpenAI.get_max_tokens("gpt-4o") == 128000
    assert AIModelOpenAI.get_max_tokens("gpt-4-turbo") == 128000
    assert AIModelOpenAI.get_max_tokens("gpt-3.5-turbo") == 16385
    assert AIModelOpenAI.get_max_tokens("gpt-3.5-turbo-aaaaaa") == 16385

    with raises(ValueError):
        AIModelOpenAI.get_max_tokens("aaaaa")
