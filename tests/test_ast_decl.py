# Author: Yiannis Charalambous

# TODO

from esbmc_ai_lib.frontend.ast_decl import (
    Declaration,
    FunctionDeclaration,
    TypeDeclaration,
    InclusionDirective,
)


def test_declaration_compare() -> None:
    declaration_1 = Declaration(name="name", type_name="type")

    declaration_2 = Declaration(name="name", type_name="type")

    assert declaration_1 == declaration_2

    declaration_3 = Declaration(name="name 1", type_name="type")

    assert declaration_1 != declaration_3

    declaration_4 = Declaration(name="name", type_name="type 1")

    assert declaration_1 != declaration_4

    declaration_5 = Declaration(name="name 1", type_name="type 1")

    assert declaration_1 != declaration_5


def test_function_declaration_compare() -> None:
    pass


def test_type_declaration_compare() -> None:
    pass


def test_inclusion_directive_compare() -> None:
    pass
