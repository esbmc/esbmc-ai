# Author: Yiannis Charalambous

from typing import Any
from typing_extensions import override
from pydantic.fields import FieldInfo
from pydantic import BaseModel

from esbmc_ai.config import Config
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.command_result import CommandResult
from esbmc_ai.component_manager import ComponentManager
from esbmc_ai.base_component import BaseComponent


class HelpConfigCommand(ChatCommand):
    """Command that prints the help messages of the acceptable config fields."""

    def __init__(self) -> None:
        super().__init__(
            command_name="help-config",
            help_message="Print information about the config fields.",
        )

    @staticmethod
    def _print_config_field(
        field_name: str, field_info: FieldInfo, level: int = 0
    ) -> None:
        """Print information about a single config field."""
        # Create indentation based on level
        indent = "\t" * (level + 1)

        # Get default value and format it
        default_value = field_info.default
        if isinstance(default_value, str) and len(default_value) > 30:
            default_value = default_value[:30] + "..."

        print(f"{indent}* {field_name}:")

        if field_info.description:
            print(f"{indent}  Description: {field_info.description}")

        # Check if this field's annotation is a BaseModel type
        field_annotation = field_info.annotation
        if field_annotation and hasattr(field_annotation, "__origin__"):
            # Handle generic types like list, dict, etc.
            field_annotation = field_annotation.__origin__

        # Check if the field type is a BaseModel subclass
        if (
            field_annotation
            and isinstance(field_annotation, type)
            and issubclass(field_annotation, BaseModel)
        ):

            print(f"{indent}  Nested fields:")
            # Recursively print fields of the BaseModel
            for (
                nested_field_name,
                nested_field_info,
            ) in field_annotation.model_fields.items():
                HelpConfigCommand._print_config_field(
                    nested_field_name, nested_field_info, level + 1
                )
        else:
            # Print default value for non-BaseModel fields
            if field_info.default is not None:
                print(f"{indent}  Default: {default_value}")

            if hasattr(field_info, "alias") and field_info.alias:
                print(f"{indent}  Alias: {field_info.alias}")

        print()

    @staticmethod
    def _print_component_config_fields(
        component_name: str, component: BaseComponent, level: int = 0
    ) -> bool:
        """Print config fields for a component if it has any.

        Returns True if the component has config fields, False otherwise.
        """
        try:
            # Try to access the component's config
            config = component.config
            if config is None:
                return False

            # Get the config class and its fields
            config_class = type(config)
            config_fields = config_class.model_fields

            if not config_fields:
                return False

            indent = "\t" * level
            print(f"{indent}{component_name}:")

            for field_name, field_info in config_fields.items():
                if not getattr(field_info, "exclude", False):
                    HelpConfigCommand._print_config_field(field_name, field_info, level)

            return True

        except (NotImplementedError, RuntimeError, AttributeError):
            # Component doesn't have config
            return False

    @staticmethod
    def _print_components_section(
        title: str, components: dict[str, BaseComponent]
    ) -> None:
        """Print a section for a group of components (builtin or addon)."""
        # First, collect components that have config
        components_with_config: list[tuple[str, BaseComponent]] = []

        for name, component in components.items():
            try:
                # Try to access config to check if it exists
                if component.config is not None:
                    components_with_config.append((name, component))
            except (NotImplementedError, RuntimeError, AttributeError):
                # Component doesn't have config, skip it
                continue

        if not components_with_config:
            # No components with config in this section
            return

        print(title)
        print()

        for name, component in components_with_config:
            HelpConfigCommand._print_component_config_fields(name, component)

    @override
    def execute(self) -> CommandResult | None:
        print("ESBMC-AI Config Fields:")
        print()

        # Get all fields from the Config model
        config_fields = Config.model_fields

        for field_name, field_info in config_fields.items():
            # Skip excluded fields (like command_name and config_file)
            if not getattr(field_info, "exclude", False):
                self._print_config_field(field_name, field_info)

        from esbmc_ai.log_utils import print_horizontal_line

        print_horizontal_line()

        # Get component manager to access builtin and addon components
        component_manager = ComponentManager()

        # Print builtin component config fields
        self._print_components_section(
            "Builtin Component Config Fields:",
            dict(component_manager.builtin_components),
        )

        print_horizontal_line()

        # Print addon component config fields
        self._print_components_section(
            "Addon Component Config Fields:", dict(component_manager.addon_components)
        )

        return None
