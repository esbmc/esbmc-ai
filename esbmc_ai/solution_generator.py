# Author: Yiannis Charalambous 2023

from typing_extensions import override
from langchain.base_language import BaseLanguageModel
from langchain.schema import BaseMessage

from esbmc_ai.chat_response import ChatResponse, FinishReason
from esbmc_ai.config import DynamicAIModelAgent

from .ai_models import AIModel
from .base_chat_interface import BaseChatInterface


class SolutionGenerator(BaseChatInterface):
    def __init__(
        self,
        ai_model_agent: DynamicAIModelAgent,
        llm: BaseLanguageModel,
        source_code: str,
        esbmc_output: str,
        ai_model: AIModel,
        scenario: str = "",
    ) -> None:
        super().__init__(
            ai_model_agent=DynamicAIModelAgent.to_chat_prompt_settings(
                ai_model_agent=ai_model_agent, scenario=scenario
            ),
            ai_model=ai_model,
            llm=llm,
        )
        self.initial_prompt = ai_model_agent.initial_prompt
        self.source_code = source_code
        self.esbmc_output = esbmc_output

        self.set_template_value("source_code", self.source_code)
        self.set_template_value("esbmc_output", self.esbmc_output)

    @override
    def compress_message_stack(self) -> None:
        # Resets the conversation - cannot summarize code
        self.messages: list[BaseMessage] = []

    @classmethod
    def get_code_from_solution(cls, solution: str) -> str:
        """Strip the source code of any leftover text as sometimes the AI model
        will generate text and formatting despite being told not to."""
        try:
            code_start: int = solution.index("```") + 3
            # Remove up until the new line, because usually there's a language
            # specification after the 3 ticks ```c...
            code_start = solution.index("\n", code_start)
            code_end: int = len(solution) - 3 - solution[::-1].index("```")
            solution = solution[code_start:code_end]
        except ValueError:
            pass
        finally:
            return solution

    def generate_solution(self) -> tuple[str, FinishReason]:
        response: ChatResponse = self.send_message(self.initial_prompt)
        solution: str = str(response.message.content)

        solution = SolutionGenerator.get_code_from_solution(solution)

        return solution, response.finish_reason
