# Author: Yiannis Charalambous

from typing import Any, DefaultDict, override
from esbmc_ai.ai_models import AIModels
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.command_result import CommandResult


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

        # Sort models into categories based on type: OpenAI, Anthropic, Ollama...
        model_types: dict[str, list[str]] = DefaultDict(list)
        for n, m in sorted(
            AIModels().ai_models.items(), key=lambda v: type(v[1]).__name__
        ):
            model_types[type(m).__name__].append(n)

        # Show in ordered list
        for model_type, models in model_types.items():
            for model_name in sorted(models):
                print(f"* {model_type}: {model_name}")

        return None
