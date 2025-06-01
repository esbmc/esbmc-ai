# Author: Yiannis Charalambous

from esbmc_ai.verifiers.esbmc import ESBMCOutput
import pytest
from os import listdir


@pytest.fixture(scope="module")
def setup_get_data() -> dict[str, ESBMCOutput]:
    data_esbmc_output: dict[str, ESBMCOutput] = {}

    for file_name in listdir("./tests/samples/esbmc_output/line_test/"):
        path: str = f"./tests/samples/esbmc_output/line_test/{file_name}"
        with open(path, "r") as file:
            data_esbmc_output[file_name] = ESBMCOutput(
                return_code=1,
                output=file.read(),
            )

    return data_esbmc_output


def test_get_source_code_err_line(setup_get_data):
    data_esbmc_output: dict[str, ESBMCOutput] = setup_get_data

    esbmc_output: ESBMCOutput = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    assert esbmc_output._get_esbmc_err_line() == 323

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    assert esbmc_output._get_esbmc_err_line() == 221

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    assert esbmc_output._get_esbmc_err_line() == 285

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    assert esbmc_output._get_esbmc_err_line() == 299

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    assert esbmc_output._get_esbmc_err_line() == 350

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    assert esbmc_output._get_esbmc_err_line() == 247


def test_esbmc_get_counter_example(setup_get_data) -> None:
    data_esbmc_output: dict[str, ESBMCOutput] = setup_get_data

    esbmc_output: ESBMCOutput = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    ce_idx: int = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    ce_idx = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    ce_idx = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    ce_idx = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    ce_idx = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    ce_idx = esbmc_output.output.find("[Counterexample]")
    assert esbmc_output._esbmc_get_counter_example() == esbmc_output.output[ce_idx:]


def test_esbmc_get_violated_property(setup_get_data) -> None:
    data_esbmc_output: dict[str, ESBMCOutput] = setup_get_data

    esbmc_output: ESBMCOutput = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    start_idx: int = esbmc_output.output.find("Violated property:")
    end_idx: int = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    start_idx = esbmc_output.output.find("Violated property:")
    end_idx = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    start_idx = esbmc_output.output.find("Violated property:")
    end_idx = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    start_idx = esbmc_output.output.find("Violated property:")
    end_idx = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    start_idx = esbmc_output.output.find("Violated property:")
    end_idx = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    start_idx = esbmc_output.output.find("Violated property:")
    end_idx = esbmc_output.output.find("VERIFICATION FAILED") - 3
    assert (
        esbmc_output._esbmc_get_violated_property()
        == esbmc_output.output[start_idx:end_idx]
    )


@pytest.fixture(scope="module")
def setup_clang_parse_errors() -> dict[str, ESBMCOutput]:
    data_esbmc_output: dict[str, ESBMCOutput] = {}

    dir_name = "./tests/samples/esbmc_output/clang_parse_errors/"
    for file_name in listdir(dir_name):
        with open(f"{dir_name}/{file_name}", "r") as file:
            data_esbmc_output[file_name] = ESBMCOutput(
                output=file.read(),
                return_code=1,
            )

    return data_esbmc_output


def test_get_clang_err_line_index(setup_clang_parse_errors) -> None:
    data_esbmc_output: dict[str, ESBMCOutput] = setup_clang_parse_errors
    print(data_esbmc_output["threading.c"])
    line = data_esbmc_output["threading.c"]._get_clang_err_line()
    assert line == 26
