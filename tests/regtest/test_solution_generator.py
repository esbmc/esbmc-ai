# Author: Yiannis Charalambous


from langchain.schema import HumanMessage, SystemMessage
from langchain_core.language_models import FakeListChatModel

from esbmc_ai.ai_models import AIModel
from esbmc_ai.verifiers.dummy_verifier import DummyVerifier
from esbmc_ai.chats.solution_generator import SolutionGenerator
from esbmc_ai.config import FixCodeScenario


def test_generate_solution(regtest) -> None:
    with open(
        "tests/samples/esbmc_output/line_test/cartpole_95_safe.c-amalgamation-80.c", "r"
    ) as file:
        esbmc_output: str = file.read()

    verifier = DummyVerifier(responses=[esbmc_output] * 2)

    chat = SolutionGenerator(
        scenarios={
            "base": FixCodeScenario(
                initial=HumanMessage(
                    "{source_code}{esbmc_output}{error_line}{error_type}"
                ),
                system=(
                    SystemMessage(
                        content="System:{source_code}{esbmc_output}{error_line}{error_type}"
                    ),
                ),
            )
        },
        verifier=verifier,
        ai_model=AIModel("test", 10000000),
        llm=FakeListChatModel(responses=["22222", "33333"]),
        source_code_format="full",
        esbmc_output_type="full",
    )

    chat.update_state("11111", esbmc_output)
    sol, res = chat.generate_solution(ignore_system_message=False)

    with regtest:
        print(res)
        print(sol)

    chat.update_state("11111", esbmc_output)
    sol, res = chat.generate_solution(ignore_system_message=False)

    with regtest:
        print(res)
        print(sol)
