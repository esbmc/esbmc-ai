# Author: Yiannis Charalambous 2023

"""Contains code for automatically repairing code using ESBMC."""

from dataclasses import dataclass, replace
from langchain_core.language_models import BaseChatModel
from typing_extensions import override
from langchain.schema import BaseMessage

from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.solution import SourceFile

from esbmc_ai.ai_models import AIModel
from esbmc_ai.verifiers.base_source_verifier import (
    SourceCodeParseError,
    VerifierTimedOutException,
)
from esbmc_ai.chats.base_chat_interface import BaseChatInterface
from esbmc_ai.verifiers.esbmc import ESBMCOutput

default_scenario: str = "base"


@dataclass
class FixCodeScenario:
    """Type for scenarios. A single scenario contains initial and system components."""

    initial: BaseMessage
    system: tuple[BaseMessage, ...]


def apply_formatting(esbmc_output: ESBMCOutput, format: str) -> str:
    """Gets the formatted output ESBMC output, based on the esbmc_output_type
    passed."""
    # Check for parsing error
    if "ERROR: PARSING ERROR" in esbmc_output.output:
        # Parsing errors are usually small in nature.
        raise SourceCodeParseError()

    if "ERROR: Timed out" in esbmc_output.output:
        raise VerifierTimedOutException()

    match format:
        case "vp":
            value: str | None = esbmc_output._esbmc_get_violated_property()
            if not value:
                raise ValueError("Not found violated property." + esbmc_output.output)
            return value
        case "ce":
            value: str | None = esbmc_output._esbmc_get_counter_example()
            if not value:
                raise ValueError("Not found counterexample.")
            return value
        case "full":
            return esbmc_output.output
        case _:
            raise ValueError(f"Not a valid ESBMC output type: {format}")


def get_source_code_formatted(
    source_code_format: str,
    source_code: str,
    esbmc_output: ESBMCOutput,
) -> str:
    """Gets the formatted output source code, based on the source_code_format
    passed."""
    match source_code_format:
        case "single":
            # Get source code error line from esbmc output
            line: int | None = esbmc_output.get_error_line_idx()
            if line:
                return source_code.splitlines(True)[line]

            raise AssertionError(
                f"error line not found in esbmc output:\n{esbmc_output}"
            )
        case "full":
            return source_code
        case _:
            raise ValueError(
                f"Not a valid format for source code: {source_code_format}"
            )


class SolutionGenerator(BaseChatInterface):
    """SolutionGenerator is a simple conversation-based automated program repair
    class. The class works in a cycle, by first calling update_state with the
    new source_code and esbmc_output, then by calling generate_solution. The
    class supports scenarios to customize the system message and initial prompt
    based on the"""

    def __init__(
        self,
        scenarios: dict[str, FixCodeScenario],
        ai_model: AIModel,
        source_code_format: str = "full",
        esbmc_output_type: str = "full",
    ) -> None:
        """Initializes the solution generator."""

        super().__init__(
            ai_model=ai_model,
            system_messages=[],  # Empty as it will be updated in the update method.
        )

        self.scenarios: dict[str, FixCodeScenario] = scenarios
        self.scenario: str = ""

        self.esbmc_output_type: str = esbmc_output_type
        self.source_code_format: str = source_code_format

        self.source_code: SourceFile | None = None
        self.source_code_formatted: str | None = None
        self.esbmc_output: ESBMCOutput | None = None
        self.invokations: int = 0

    @override
    def compress_message_stack(self) -> None:
        # Resets the conversation - cannot summarize code
        # If generate_solution is called after this point, it will start new
        # with the currently set state.
        self.messages: list[BaseMessage] = []
        self.invokations = 0

    @staticmethod
    def extract_code_from_solution(solution: str) -> str:
        """Strip the source code of any leftover text as sometimes the AI model
        will generate text and formatting despite being told not to."""
        try:
            code_start: int = solution.index("```") + 3
            assert code_start != -1

            # Remove up until the new line, because usually there's a language
            # specification after the 3 ticks ```c...
            code_start = solution.index("\n", code_start) + 1
            assert code_start != -1

            code_end: int = solution[::-1].index("```")
            assert code_start != -1

            # -4 = 3 backticks and also the \n before the backticks.
            code_end: int = len(solution) - 4 - code_end
            # +1 because of edge cases as in test_get_code_from_solution
            assert code_start <= code_end + 1

            solution = solution[code_start:code_end]
        except (ValueError, AssertionError):
            pass
        return solution

    def update_state(
        self, source_file: SourceFile, verifier_output: ESBMCOutput
    ) -> None:
        """Updates the latest state of the code and ESBMC output. It also updates
        the scenario, which is the type of error that ESBMC has shown. This should be
        called before generate_solution."""

        self.scenario = verifier_output.get_error_type()
        if not self.scenario:
            self.scenario = default_scenario

        self.source_code_raw = source_file.content

        # Format ESBMC output
        try:
            self.esbmc_output = replace(
                verifier_output,
                output=apply_formatting(
                    esbmc_output=verifier_output,
                    format=self.esbmc_output_type,
                ),
            )
        except SourceCodeParseError:
            # When clang output is displayed, show it entirely as it doesn't get very
            # big.
            self.esbmc_output = verifier_output

        # Format source code
        self.source_code_formatted = get_source_code_formatted(
            source_code_format=self.source_code_format,
            source_code=source_file.content,
            esbmc_output=verifier_output,
        )

    def _get_system_messages(
        self, override_scenario: str | None = None
    ) -> tuple[BaseMessage, ...]:
        if override_scenario:
            system_messages = self.scenarios[override_scenario].system
        else:
            assert self.scenario, "Call update or set the scenario"
            if self.scenario in self.scenarios:
                system_messages = self.scenarios[self.scenario].system
            else:
                system_messages = self.scenarios[default_scenario].system

        assert isinstance(system_messages, tuple)
        assert all(isinstance(msg, BaseMessage) for msg in system_messages)
        return system_messages

    def _get_initial_message(self, override_scenario: str | None = None) -> BaseMessage:
        if override_scenario:
            return self.scenarios[override_scenario].initial
        else:
            assert self.scenario, "Call update or set the scenario"
            if self.scenario in self.scenarios:
                return self.scenarios[self.scenario].initial
            else:
                return self.scenarios[default_scenario].initial

    def generate_solution(
        self,
        override_scenario: str | None = None,
        ignore_system_message: bool = False,
    ) -> tuple[str, FinishReason]:
        """Prompts the LLM to repair the source code using the verifier output.
        If this is the first time the method is called, the system message will
        be sent to the LLM, unless ignore_system_message is True. Then the
        initial prompt will be sent.

        In subsequent invokations of generate_solution, the initial prompt will
        be used only.

        So the system messages and initial message should each include at least
        {source_code} and {esbmc_output} so that they are substituted into the
        message.

        Queries the AI model to get a solution. Accepts an override scenario
        parameter, in which case the scenario won't be resolved automatically."""

        assert (
            self.source_code_raw is not None
            and self.source_code_formatted is not None
            and self.esbmc_output is not None
            and self.scenario is not None
        ), "Call update_state before calling generate_solution."

        # Show system message
        if not ignore_system_message and self.invokations <= 0:
            # Get scenario system messages and push it to message stack. Don't
            # push to system message stack because we want to regenerate from
            # the beginning at every reset.
            system_messages: tuple[BaseMessage, ...] = self._get_system_messages(
                override_scenario=override_scenario
            )
            if len(system_messages) > 0:
                self.push_to_message_stack(system_messages)

        # Get scenario initial message and push it to message stack
        self.push_to_message_stack(
            self._get_initial_message(override_scenario=override_scenario)
        )

        self.invokations += 1

        error_type: str | None = self.esbmc_output.get_error_type()

        # Apply template substitution to message stack
        self.apply_template_value(
            **self.get_canonical_template_keys(
                source_code=self.source_code_formatted,
                esbmc_output=self.esbmc_output.output,
                error_line=str(self.esbmc_output.get_error_line()),
                error_type=error_type if error_type else "unknown error",
            )
        )

        # Generate the solution
        response: ChatResponse = self.send_message()
        solution: str = str(response.message.content)

        solution = SolutionGenerator.extract_code_from_solution(solution)

        # Post process source code
        # If source code passed to LLM is formatted then we need to recombine to
        # full source code before giving to ESBMC
        match self.source_code_format:
            case "single":
                # Get source code error line from esbmc output
                line: int | None = self.esbmc_output.get_error_line_idx()
                assert line, (
                    "fix code command: error line could not be found to apply "
                    "brutal patch replacement"
                )
                solution = SourceFile.apply_line_patch(
                    self.source_code_raw, solution, line, line
                )

        return solution, response.finish_reason


class ReverseOrderSolutionGenerator(SolutionGenerator):
    """SolutionGenerator that shows the source code and verifier output state in
    reverse order."""

    @override
    def send_message(self, message: str | None = None) -> ChatResponse:
        # Reverse the messages
        messages: list[BaseMessage] = self.messages.copy()
        self.messages.reverse()

        response: ChatResponse = super().send_message(message)

        # Add to the reversed message the new message received by the LLM.
        messages.append(self.messages[-1])
        # Restore
        self.messages = messages

        return response


class LatestStateSolutionGenerator(SolutionGenerator):
    """SolutionGenerator that only shows the latest source code and verifier
    output state."""

    @override
    def generate_solution(
        self,
        override_scenario: str | None = None,
        ignore_system_message: bool = False,
    ) -> tuple[str, FinishReason]:
        # Backup message stack and clear before sending base message. We want
        # to keep the message stack intact because we will print it with
        # print_raw_conversation.
        messages: list[BaseMessage] = self.messages
        self.messages: list[BaseMessage] = []
        solution, finish_reason = super().generate_solution(
            override_scenario=override_scenario,
            ignore_system_message=ignore_system_message,
        )
        # Append last messages to the messages stack
        messages.extend(self.messages)
        # Restore
        self.messages = messages
        return solution, finish_reason
