# Author: Yiannis Charalambous


from typing import Any
from typing_extensions import override

from esbmc_ai.addon_loader import Config, AddonLoader
from esbmc_ai.config_field import ConfigField
from esbmc_ai.chat_command import ChatCommand


class HelpConfigCommand(ChatCommand):
    """Command that prints the help messages of the acceptable config fields."""

    def __init__(self) -> None:
        super().__init__(
            command_name="help-config",
            help_message="Print information about the config fields.",
        )

    @staticmethod
    def _print_config_field(field: ConfigField) -> None:
        value_type: type = type(field.default_value)
        # Default value: for strings enforce a limit
        default_value: Any = field.default_value
        if value_type is str and len(field.default_value) > 30:
            default_value = field.default_value[:30] + "..."

        print(
            f"\t* {field.name}: "
            f'{value_type.__name__} = "{default_value}" - {field.help_message}'
        )

    @override
    def execute(self, **kwargs: Any | None) -> Any:
        _ = kwargs

        addon_fields: list[ConfigField] = []

        print("ESBMC-AI Config Fields:")
        for field in Config()._fields:
            split_field_name: list[str] = field.name.split(".")
            if (
                len(split_field_name) > 1
                and split_field_name[0] == AddonLoader.addon_prefix
            ):
                addon_fields.append(field)
            else:
                self._print_config_field(field)

        if addon_fields:
            print("\nESBMC-AI Addon Fields:")
            for field in addon_fields:
                self._print_config_field(field)

        return None
