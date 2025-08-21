# Author: Yiannis Charalambous

from typing import Any
from esbmc_ai import ChatCommand
from esbmc_ai.command_result import CommandResult
from esbmc_ai import AIModels


class ReloadAIModelsCommand(ChatCommand):
    def __init__(self) -> None:
        super().__init__(
            command_name="reload-models",
            authors="",
            help_message="Refreshes the list of models by pulling the model definitions from online.",
        )

    def execute(self, **kwargs: Any | None) -> CommandResult | None:
        _ = kwargs

        self.logger.info("Reloading AI Models...")
        AIModels().load_default_models(self.get_config_value("api_keys"))
