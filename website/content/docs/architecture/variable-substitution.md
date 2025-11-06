---
title: Variable Substitution System
weight: 2
---

ESBMC-AI includes a powerful variable substitution system that allows dynamic content replacement in AI model prompts and chat templates. This system enables customizable prompt engineering by substituting predefined variables with actual values at runtime.

## Overview

The variable substitution system is implemented through the `AIModel.safe_substitute()` method and is used by the `BaseChatInterface.apply_template_value()` method to replace template variables in system messages and conversation history.

## Template Syntax

Variables in templates use the **dollar sign (`$`) syntax**:

```
$variable_name
```

### Examples

```python
# System message with template variables
SystemMessage(content="Analyze this code: $source_code")
SystemMessage(content="Oracle found: $oracle_output")
SystemMessage(content="Error on line $error_line: $error_type")
```

When `apply_template_value()` is called with values:
```python
chat.apply_template_value(
    source_code="int main() { return 0; }",
    oracle_output="No errors found",
    error_line="15",
    error_type="null pointer dereference"
)
```

The templates become:
```
Analyze this code: int main() { return 0; }
Oracle found: No errors found
Error on line 15: null pointer dereference
```

## Escape Characters

To include a literal dollar sign in your template without triggering substitution, use **double dollar signs (`$$`)**:

```python
SystemMessage(content="Cost is $$50 but error is in $source_code")
```

With `source_code="main.c"`, this becomes:
```
Cost is $50 but error is in main.c
```

## Canonical Template Variables

ESBMC-AI defines standard template variables through the `get_canonical_template_keys()` method:

| Variable | Description |
|----------|-------------|
| `$source_code` | The source code being analyzed |
| `$oracle_output` | Output from the verifier oracle |
| `$error_line` | Line number where error occurred |
| `$error_type` | Type of error detected |

### Usage Example

```python
# Get canonical template variables
template_vars = chat.get_canonical_template_keys(
    source_code="int main() { int *p = NULL; *p = 5; }",
    oracle_output="Dereference failure: pointer invalid",
    error_line="1",
    error_type="null pointer dereference"
)

# Apply to templates
chat.apply_template_value(**template_vars)
```

## Implementation Details

### Safe Substitution

The `safe_substitute()` method ensures:
- Undefined variables are left unchanged (no errors thrown)
- Only valid variable names are substituted
- Escape sequences are properly handled

### Method Signature

```python
@classmethod
def safe_substitute(cls, content: str, **values: Any) -> str:
    """Safe template substitution. Replaces $var with provided values,
    leaves undefined $vars unchanged."""
```

### Template Application

The `apply_template_value()` method applies substitution to:
1. **System messages** - Initial prompt templates
2. **Message stack** - Conversation history

```python
def apply_template_value(self, **kwargs: str) -> None:
    """Will substitute variables in the message stack and system messages.
    The substitution is permanent."""
```

## Usage in Commands

Commands typically use the canonical template system:

```python
class FixCodeCommand(ChatCommand):
    def execute(self, source_code: str, oracle_output: str) -> None:
        # Apply template values using canonical keys
        template_values = self.chat.get_canonical_template_keys(
            source_code=source_code,
            oracle_output=oracle_output,
            error_line=self.get_error_line(),
            error_type=self.get_error_type()
        )

        self.chat.apply_template_value(**template_values)

        # Send message to AI model
        response = self.chat.send_message("Please fix the code.")
```

## Best Practices

1. **Use canonical variables** when possible for consistency
2. **Escape dollar signs** when you need literal `$` characters
3. **Test templates** with various input values
4. **Document custom variables** in your command or verifier
5. **Validate substitution results** in tests

## Testing Variable Substitution

Example test pattern:

```python
def test_template_substitution():
    system_messages = [
        SystemMessage(content="Fix this: $source_code"),
        SystemMessage(content="Error: $error_type")
    ]
    
    chat = BaseChatInterface(system_messages=system_messages, ai_model=mock_model)
    chat.apply_template_value(source_code="buggy.c", error_type="segfault")
    
    assert chat._system_messages[0].content == "Fix this: buggy.c"
    assert chat._system_messages[1].content == "Error: segfault"
```

This system provides flexible prompt engineering while maintaining type safety and preventing common template injection issues.