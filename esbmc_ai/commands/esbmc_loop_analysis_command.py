# Author: Yiannis Charalambous

import os
from pathlib import Path
from subprocess import run, TimeoutExpired
from typing import Any, override

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import Field

from esbmc_ai.ai_models import AIModel
from esbmc_ai.base_component import BaseComponentConfig
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.chats.key_template_renderer import KeyTemplateRenderer
from esbmc_ai.chats.template_key_provider import GenericTemplateKeyProvider
from esbmc_ai.command_result import CommandResult
from esbmc_ai.component_manager import ComponentManager
from esbmc_ai.loading_widget import BaseLoadingWidget, LoadingWidget
from esbmc_ai.solution import Solution, SourceFile
from esbmc_ai.verifiers.esbmc import ESBMC, ESBMCLoopParser, ESBMCLoops


class ESBMCLoopAnalysisCommandResult(CommandResult):
    """Returned by the LoopAnalysisCommand."""

    def __init__(
        self,
        successful: bool,
        loops: ESBMCLoops | None = None,
        loop_bounds: dict[int, int] | None = None,
    ) -> None:
        super().__init__()
        self._successful: bool = successful
        self.loops: ESBMCLoops | None = loops
        self.loop_bounds: dict[int, int] | None = loop_bounds

    @property
    @override
    def successful(self) -> bool:
        return self._successful

    @override
    def __str__(self) -> str:
        if self._successful:
            if self.loop_bounds:
                result = "Loop Analysis Results:\n\n"
                pairs = []
                determined_count = 0
                if self.loops:
                    for loop in self.loops.loops:
                        bound = self.loop_bounds.get(loop.loop_idx, -1)
                        if bound != -1:
                            result += (
                                f"Loop {loop.loop_idx}: {loop.file_name}:{loop.line_number} "
                                f"in {loop.function_name} -> Max iterations: {bound}\n"
                            )
                            pairs.append(f"{loop.loop_idx}:{bound}")
                            determined_count += 1
                        else:
                            result += (
                                f"Loop {loop.loop_idx}: {loop.file_name}:{loop.line_number} "
                                f"in {loop.function_name} -> Max iterations: undetermined\n"
                            )

                    # Add summary line
                    total_loops = len(self.loops)
                    result += (
                        f"\nFound {total_loops} loop{'s' if total_loops != 1 else ''}, "
                    )
                    result += f"{determined_count} with determined bounds\n"

                # Add final line with compact format (only determined bounds)
                if pairs:
                    result += "\n" + ",".join(pairs)
                return result
            else:
                return "No loops found in the source code."
        return "Loop analysis failed."


class LoopAnalysisCommandConfig(BaseComponentConfig):
    temperature: float = Field(
        default=0,
        description="The temperature of the LLM for the loop analysis command. "
        "Separate from global value since usually this should always be a low "
        "value.",
    )

    system_prompt: str = Field(
        default=(
            "You are a program analysis assistant. You will be shown source code "
            "and a list of loops detected in the code. Your task is to analyze each "
            "loop and determine the maximum number of iterations it will execute. "
            "Return your analysis as a JSON object mapping loop_idx to max_iterations. "
            'For example: {"1": 10, "2": 100}. Only return the JSON object, nothing else.'
        ),
        description="System prompt for the LLM.",
    )

    prompt: str = Field(
        default=(
            "Analyze the following source code and determine the maximum number of "
            "iterations for each loop.\n\n"
            "Source code:\n```c\n{{solution.files[0].content}}\n```\n\n"
            "Detected loops:\n"
            "{% for detected_loop in loops.loops %}"
            "- Loop {{detected_loop.loop_idx}}: {{detected_loop.file_name}}:{{detected_loop.line_number}} "
            "in function {{detected_loop.function_name}}\n"
            "{% endfor %}\n\n"
            "Return a JSON object mapping loop_idx to maximum iterations. "
            "If a loop's bound cannot be determined, use -1. "
            'Format: {"loop_idx": max_iterations, ...}'
        ),
        description="Prompt template for loop bound analysis.",
    )


class LoopAnalysisCommand(ChatCommand):
    """Command for analyzing loops in code and determining iteration bounds."""

    def __init__(self) -> None:
        super().__init__(
            command_name="esbmc-loop-analysis",
            help_message="Analyzes loops in code and determines maximum iteration bounds using LLM.",
        )
        self._config: LoopAnalysisCommandConfig = LoopAnalysisCommandConfig()
        self.anim: BaseLoadingWidget

    @classmethod
    def _get_config_class(cls) -> type[BaseComponentConfig]:
        """Return the config class for this component."""
        return LoopAnalysisCommandConfig

    @property
    @override
    def config(self) -> BaseComponentConfig:
        return self._config

    @config.setter
    def config(self, value: BaseComponentConfig) -> None:
        assert isinstance(value, LoopAnalysisCommandConfig)
        self._config = value

    @override
    def execute(self) -> ESBMCLoopAnalysisCommandResult:
        """Execute the loop analysis command."""
        # Load source file
        source_file: SourceFile = SourceFile.load(
            self.global_config.solution.filenames[0],
            Path(os.getcwd()),
        )

        self.anim = (
            LoadingWidget() if self.global_config.loading_hints else BaseLoadingWidget()
        )

        solution: Solution = Solution([])
        solution.add_source_file(source_file)

        self.logger.info(f"LoopAnalysisConfig: {self._config}")

        # Get ESBMC verifier (do not use verifier from config)
        verifier: Any = ComponentManager().get_verifier("esbmc")
        assert isinstance(verifier, ESBMC)

        # Run ESBMC with --show-loops
        with self.anim("Running ESBMC with --show-loops..."):
            loops_output = self._run_esbmc_show_loops(verifier, solution)

        # Parse loops
        with self.anim("Parsing loop information..."):
            all_loops = ESBMCLoopParser.parse_loops(loops_output)
            self.logger.info(f"Found {len(all_loops)} total loops")

            # Filter to only solution files
            loops = all_loops.filter_by_solution(solution)
            self.logger.info(f"Found {len(loops)} loops in solution files")

        if len(loops) == 0:
            self.logger.info("No loops found in source files")
            return ESBMCLoopAnalysisCommandResult(True, loops, {})

        # Ask LLM to analyze loop bounds
        with self.anim("Analyzing loop bounds with LLM..."):
            loop_bounds = self._analyze_loop_bounds(solution, loops)

        self.logger.info(f"Loop bounds analysis: {loop_bounds}")

        return ESBMCLoopAnalysisCommandResult(True, loops, loop_bounds)

    def _run_esbmc_show_loops(self, verifier: ESBMC, solution: Solution) -> str:
        """
        Run ESBMC with --show-loops flag to get loop information.

        Args:
            verifier: ESBMC verifier instance
            solution: Solution containing source files

        Returns:
            Raw output from ESBMC --show-loops
        """
        # Save solution to temp directory for ESBMC
        temp_solution = solution.save_temp()

        # Build ESBMC command
        esbmc_cmd = [str(verifier.esbmc_path), "--show-loops"]

        # Add source files
        esbmc_cmd.append("--input-file")
        esbmc_cmd.extend(
            str(file.file_path) for file in temp_solution.get_files_by_ext(["c", "cpp"])
        )

        # Add include directories
        esbmc_cmd.extend("-I" + str(d) for d in temp_solution.include_dirs.keys())

        # Run ESBMC
        self.logger.debug(f"Running ESBMC command: {' '.join(esbmc_cmd)}")

        try:
            result = run(
                esbmc_cmd,
                capture_output=True,
                text=True,
                cwd=temp_solution.base_dir,
                timeout=30,
                check=False,
            )
            # Combine stdout and stderr as ESBMC may output to either
            output = result.stdout + result.stderr
            return output
        except TimeoutExpired:
            self.logger.error("ESBMC --show-loops timed out")
            raise

    def _analyze_loop_bounds(
        self, solution: Solution, loops: ESBMCLoops
    ) -> dict[int, int]:
        """
        Use LLM to analyze loop bounds.

        Args:
            solution: Solution containing source code
            loops: ESBMCLoops object with detected loops

        Returns:
            Dictionary mapping loop_idx to max iterations
        """
        # Create AI model
        ai_model = AIModel.get_model(
            model=self.global_config.ai_model.id,
            temperature=self._config.temperature,
            url=self.global_config.ai_model.base_url,
        )

        # Create template renderer
        key_template_renderer = KeyTemplateRenderer(
            messages=[
                ("system", self._config.system_prompt),
                ("human", self._config.prompt),
            ],
            key_provider=GenericTemplateKeyProvider(),
        )

        # Format messages with solution and loops
        messages = key_template_renderer.format_messages(
            solution=solution,
            loops=loops,
        )

        # Generate response from LLM
        response: BaseMessage = ai_model.invoke(messages)
        response_text = str(response.content)

        self.logger.debug(f"LLM response: {response_text}")

        # Parse JSON from response
        json_parser = JsonOutputParser()
        try:
            loop_bounds_raw = json_parser.parse(response_text)

            # Convert string keys to integers
            loop_bounds: dict[int, int] = {
                int(k): int(v) for k, v in loop_bounds_raw.items()
            }

            return loop_bounds

        except Exception as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {}
