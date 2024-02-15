# Author: Yiannis Charalambous

import json
from dataclasses import dataclass
from typing import Any
from typing_extensions import override

from esbmc_ai_config.models.config_loader import ConfigLoader

__ALLOWED_JSON_TYPES = bool | float | int | str | list | dict


@dataclass
class JsonConfigNode:
    default_value: "__ALLOWED_JSON_TYPES" = ""
    value: "__ALLOWED_JSON_TYPES" = ""
    """The value in the config. If type does not match the `default_value` type and the
    `create_missing_fields` is set to `True`, then the `default_value` will be used."""
    is_optional: bool = False
    """Will not load the config if the value is not specified by the user. If
    true will assign default_value."""
    show_in_config: bool = True
    """Show this field in the config tool UI."""

    def __getitem__(self, subscript):
        """Allow indexing the default_values if they are a list or a dict.
        Can accept an int for default_values that are list or dict.
        Can accept a str for default_values that are dict."""
        # NOTE TestMe
        if isinstance(subscript, int) and isinstance(self.default_value, list):
            # Using list and int indexing
            return self.default_value[subscript]
        elif isinstance(subscript, str) and isinstance(self.default_value, dict):
            # Using str and dictionary indexing
            return self.default_value[subscript]
        raise IndexError(
            f"Invalid type of subscript: {type(subscript)}: type of value: {type(self.default_value)}"
        )


class JsonConfigLoader(ConfigLoader):
    def __init__(
        self,
        file_path: str = "~/.config/esbmc-ai.json",
        root_node: JsonConfigNode = JsonConfigNode(
            default_value={
                "esbmc_path": JsonConfigNode("~/.local/bin/esbmc"),
                "ai_model": JsonConfigNode("gpt-3.5-turbo-16k"),
                "ai_custom": JsonConfigNode({}),
                "allow_successful": JsonConfigNode(True),
                "esbmc_params": JsonConfigNode(
                    [
                        "--interval-analysis",
                        "--goto-unwind",
                        "--unlimited-goto-unwind",
                        "--k-induction",
                        "--state-hashing",
                        "--add-symex-value-sets",
                        "--k-step",
                        "2",
                        "--floatbv",
                        "--unlimited-k-steps",
                        "--memory-leak-check",
                        "--context-bound",
                        "2",
                    ]
                ),
                "consecutive_prompt_delay": JsonConfigNode(20),
                "temp_auto_clean": JsonConfigNode(True),
                "temp_file_dir": JsonConfigNode("~/.cache/esbmc-ai"),
                "loading_hints": JsonConfigNode(True),
                # TODO Finish fields
            }
        ),
        create_missing_fields: bool = False,
    ) -> None:
        assert file_path.endswith(
            ".json"
        ), f"{self.file_path} is not a valid json file."

        self.root_node: JsonConfigNode = root_node
        self.values: dict = {}

        super().__init__(
            file_path=file_path,
            create_missing_fields=create_missing_fields,
        )

    @override
    def save(self) -> None:
        raise NotImplementedError()

    @override
    def _create_default_file(self) -> None:
        raise NotImplementedError()

    @override
    def _read_fields(self, create_missing_fields: bool = False) -> None:
        """Parses the JSON config and loads all the values recursively. The self.values should
        map directly to how the self.node values are laid out.

        Arg:
            create_missing_field: bool - Will not give an error when an invalid/missing field
            is encountered, will instead initialize it to the default value."""
        self.json_content: dict = json.loads(self.content)

        def init_node_value(node: JsonConfigNode, json_node: "__ALLOWED_JSON_TYPES"):
            # Check if the value and default_value match type
            if type(json_node) is not type(node.default_value):
                # Initialize with default_value
                node.value = node.default_value
            elif type(node.default_value) is dict[str, JsonConfigNode]:
                assert isinstance(json_node, dict)
                # Init children
                for child_key, child_node in node.default_value:
                    assert isinstance(child_key, str)
                    assert isinstance(child_node, JsonConfigNode)
                    init_node_value(child_node, json_node[child_key])
            elif isinstance(node.default_value, list):
                assert isinstance(json_node, list)
                node.value = json_node
            else:
                assert type(json_node) is type(node.default_value)
                node.value = json_node

        init_node_value(self.root_node, self.json_content)

        raise Exception(self.root_node.value)
