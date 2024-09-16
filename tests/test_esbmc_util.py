# Author: Yiannis Charalambous

import pytest
from os import listdir

from esbmc_ai.esbmc_util import ESBMCUtil


@pytest.fixture(scope="module")
def setup_get_data() -> dict[str, str]:
    data_esbmc_output: dict[str, str] = {}

    for file_name in listdir("./tests/samples/esbmc_output/line_test/"):
        path: str = f"./tests/samples/esbmc_output/line_test/{file_name}"
        with open(path, "r") as file:
            data_esbmc_output[file_name] = file.read()

    return data_esbmc_output


def test_get_source_code_err_line(setup_get_data):
    data_esbmc_output: dict[str, str] = setup_get_data

    esbmc_output: str = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 323

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 221

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 285

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 299

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 350

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    assert ESBMCUtil.get_source_code_err_line(esbmc_output) == 247


def test_esbmc_get_counter_example(setup_get_data) -> None:
    data_esbmc_output: dict[str, str] = setup_get_data

    esbmc_output: str = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    ce_idx: int = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    ce_idx = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    ce_idx = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    ce_idx = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    ce_idx = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    ce_idx = esbmc_output.find("[Counterexample]")
    assert ESBMCUtil.esbmc_get_counter_example(esbmc_output) == esbmc_output[ce_idx:]


def test_esbmc_get_violated_property(setup_get_data) -> None:
    data_esbmc_output: dict[str, str] = setup_get_data

    esbmc_output: str = data_esbmc_output["cartpole_48_safe.c-amalgamation-6.c"]
    start_idx: int = esbmc_output.find("Violated property:")
    end_idx: int = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_92_safe.c-amalgamation-14.c"]
    start_idx = esbmc_output.find("Violated property:")
    end_idx = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_95_safe.c-amalgamation-80.c"]
    start_idx = esbmc_output.find("Violated property:")
    end_idx = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["cartpole_26_safe.c-amalgamation-74.c"]
    start_idx = esbmc_output.find("Violated property:")
    end_idx = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["robot_5_safe.c-amalgamation-13.c"]
    start_idx = esbmc_output.find("Violated property:")
    end_idx = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )

    esbmc_output = data_esbmc_output["vdp_1_safe.c-amalgamation-28.c"]
    start_idx = esbmc_output.find("Violated property:")
    end_idx = esbmc_output.find("VERIFICATION FAILED") - 3
    assert (
        ESBMCUtil.esbmc_get_violated_property(esbmc_output)
        == esbmc_output[start_idx:end_idx]
    )


@pytest.fixture(scope="module")
def setup_clang_parse_errors() -> dict[str, str]:
    data_esbmc_output: dict[str, str] = {}

    dir_name = "./tests/samples/esbmc_output/clang_parse_errors/"
    for file_name in listdir(dir_name):
        with open(f"{dir_name}/{file_name}", "r") as file:
            data_esbmc_output[file_name] = file.read()

    return data_esbmc_output


def test_get_clang_err_line_index(setup_clang_parse_errors) -> None:
    data_esbmc_output = setup_clang_parse_errors
    print(data_esbmc_output["threading.c"])
    line = ESBMCUtil.get_clang_err_line(data_esbmc_output["threading.c"])
    assert line == 26
