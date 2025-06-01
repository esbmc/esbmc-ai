# Author: Yiannis Charalambous

"""This module contains methods to interact and validate prompts."""


def validate_prompt_template_conversation(prompt_template: list[dict]) -> bool:
    """Used to validate if a prompt template conversation is of the correct format
    in the config before loading it."""

    for msg in prompt_template:
        if (
            not isinstance(msg, dict)
            or "content" not in msg
            or "role" not in msg
            or not isinstance(msg["content"], str)
            or not isinstance(msg["role"], str)
        ):
            return False
    return True


def validate_prompt_template(conv: dict[str, list[dict]]) -> bool:
    """Used to check if a prompt template (contains conversation and initial message) is
    of the correct format."""
    if (
        "initial" not in conv
        or not isinstance(conv["initial"], str)
        or "system" not in conv
        or not validate_prompt_template_conversation(conv["system"])
    ):
        return False
    return True
