# Author: Yiannis Charalambous

from typing import Any, override
from esbmc_ai.ai_models import AIModels
from esbmc_ai.commands.chat_command import ChatCommand
from esbmc_ai.commands.command_result import CommandResult


class ListModelsCommand(ChatCommand):
    """Command to list all models that are available."""

    def __init__(self) -> None:
        super().__init__(
            command_name="list-models",
            help_message="Lists all available AI models.",
            authors="",
        )

    @override
    def execute(self, **kwargs: Any | None) -> CommandResult | None:
        _ = kwargs

        for name, model in AIModels().ai_models.items():
            print(f"* {type(model).__name__}: {name}")

        return None
