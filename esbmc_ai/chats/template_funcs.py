# Author: Yiannis Charalambous

"""Contains mappings for template values and filters that are used by
KeyTemplateRenderer prompt templates."""

from typing import Any

from esbmc_ai.issue import VerifierIssue


def get_func_mapping():
    return _func_mapping


def _is_verifier_issue(obj: Any) -> bool:
    return isinstance(obj, VerifierIssue)


_func_mapping: dict[str, Any] = {
    "is_verifier_issue": _is_verifier_issue,
}


# TODO Figure out how to integrate into KeyTemplateRenderer

# def get_filter_mapping():
#     return _filter_mapping


# def _isinstance_filter(obj: object, classinfo: type) -> bool:
#     return isinstance(obj, classinfo)


# _filter_mapping: dict[str, Callable] = {
#     "isinstance": _isinstance_filter,
# }
