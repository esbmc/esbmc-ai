# Author: Yiannis Charalambous

from typing import Any, override
from pydantic.fields import FieldInfo
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.config import get_config_key
from esbmc_ai.command_result import CommandResult
from esbmc_ai.component_manager import ComponentManager


class DebugConfigViewCommand(ChatCommand):
    """Displays all loaded config values."""

    def __init__(self) -> None:
        super().__init__(
            command_name="debug-view-config",
            authors="",
            help_message="Used for debug to view the current config state.",
        )

    @staticmethod
    def _format_value(value: Any, indent: str = "  ") -> None:
        """Format and print a config value with appropriate formatting."""
        if isinstance(value, dict):
            if value:
                for k, v in value.items():
                    print(f"{indent}{k}: {v}")
            else:
                print(f"{indent}(empty)")
        elif isinstance(value, (list, tuple)):
            if value:
                for item in value:
                    print(f"{indent}- {item}")
            else:
                print(f"{indent}(empty)")
        else:
            print(f"{indent}{value}")

    def _print_config_section(
        self,
        config_dict: dict[str, Any],
        model_fields: dict[str, FieldInfo] | None = None,
        indent: str = "",
    ) -> None:
        """Print a config dictionary with config file keys as names."""
        for field_name, value in config_dict.items():
            if model_fields and field_name in model_fields:
                display_name = get_config_key(field_name, model_fields[field_name])
            else:
                display_name = field_name
            print(f"\n{indent}{display_name}:")
            self._format_value(value, indent + "  ")

    @override
    def execute(self) -> CommandResult | None:
        print("\n" + "=" * 80)
        print("GLOBAL CONFIGURATION")
        print("=" * 80)

        self._print_config_section({"Config File": self.global_config.config_file})
        self._print_config_section(
            self.global_config.model_dump(),
            model_fields=type(self.global_config).model_fields,
        )

        print("\n" + "=" * 80)
        print("BUILTIN COMPONENT CONFIGURATIONS")
        print("=" * 80)

        cm = ComponentManager()
        builtin_components = cm.builtin_components
        if not builtin_components:
            print("\n(No builtin components)")
        else:
            for name, component in builtin_components.items():
                print(f"\n{name}:")
                try:
                    if component.config:
                        self._print_config_section(
                            component.config.model_dump(),
                            model_fields=type(component.config).model_fields,
                            indent="  ",
                        )
                    else:
                        print("  (no config)")
                except NotImplementedError:
                    print("  (no config)")

        print("\n" + "=" * 80)
        print("ADDON COMPONENT CONFIGURATIONS")
        print("=" * 80)

        addon_components = cm.addon_components
        if not addon_components:
            print("\n(No addon components)")
        else:
            for name, component in addon_components.items():
                print(f"\n{name}:")
                try:
                    if component.config:
                        self._print_config_section(
                            component.config.model_dump(),
                            model_fields=type(component.config).model_fields,
                            indent="  ",
                        )
                    else:
                        print("  (no config)")
                except NotImplementedError:
                    print("  (no config)")

        print("\n" + "=" * 80 + "\n")

        return None
