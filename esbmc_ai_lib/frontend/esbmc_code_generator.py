# Author: Yiannis Charalambous

import clang.cindex as cindex

from typing import Optional

from .ast import ClangAST
from .ast_decl import Declaration, TypeDeclaration, FunctionDeclaration


class ESBMCCodeGenerator(object):
    """Generates code using ClangAST for use in ESBMC scripts."""

    _primitives_base_defaults: dict[str, str] = {
        # Bool
        "bool": "__VERIFIER_nondet_bool()",
        # Decimals
        "float": "__VERIFIER_nondet_float()",
        "double": "__VERIFIER_nondet_double()",
        "long double": "__VERIFIER_nondet_double()",
        # Char
        "char": "__VERIFIER_nondet_char()",
        "signed char": "__VERIFIER_nondet_schar()",
        "unsigned char": "__VERIFIER_nondet_uchar()",
        # Int
        "int": "__VERIFIER_nondet_int()",
        "signed int": "__VERIFIER_nondet_int()",
        "unsigned int": "__VERIFIER_nondet_uint()",
        # Short
        "short": "__VERIFIER_nondet_short()",
        "signed short": "__VERIFIER_nondet_short()",
        "unsigned short": "__VERIFIER_nondet_ushort()",
        # Short (int)
        "short int": "__VERIFIER_nondet_short()",
        "signed short int": "__VERIFIER_nondet_short()",
        "unsigned short int": "__VERIFIER_nondet_ushort()",
        # Long
        "long": "__VERIFIER_nondet_long()",
        "signed long": "__VERIFIER_nondet_long()",
        "unsigned long": "__VERIFIER_nondet_ulong()",
        # Long (int)
        "long int": "__VERIFIER_nondet_long()",
        "signed long int": "__VERIFIER_nondet_long()",
        "unsigned long int": "__VERIFIER_nondet_ulong()",
        # Long Long
        "long long": "__VERIFIER_nondet_long()",
        "signed long long": "__VERIFIER_nondet_long()",
        "unsigned long long": "__VERIFIER_nondet_ulong()",
        # Long Long (int)
        "long long int": "__VERIFIER_nondet_long()",
        "signed long long int": "__VERIFIER_nondet_long()",
        "unsigned long long int": "__VERIFIER_nondet_ulong()",
    }
    """Assign the following values for each primitive data type."""

    ast: ClangAST

    def __init__(self, ast: ClangAST) -> None:
        self.ast = ast

    def statement_primitive_construct(
        self, d: Declaration, result_name: str = ""
    ) -> str:
        """Returns the primitive construction of a variable/value. Will be
        __VERIFIER_nondet_X(). The list of available ESBMC functions is taken
        from https://github.com/esbmc/esbmc/blob/master/src/clang-c-frontend/clang_c_language.cpp
        """

        value: str = ESBMCCodeGenerator._primitives_base_defaults[d.type_name]

        return value

    def statement_type_construct(
        self,
        d: TypeDeclaration,
        assign_to: str = "",
    ) -> str:
        """Constructs a statement to  that is represented by decleration d."""
        assert d.cursor

        cmd: str

        # Check if primitive type and return nondet value.
        if len(list(d.cursor.get_children())) == 0:
            return self.statement_primitive_construct(d)

        cmd = "{"

        # Loop through each element of the data type.
        elements: list[str] = []
        for element in d.elements:
            # Check if element is a primitive type. If not, it will need to be
            # further broken.
            if element.type_name in self._primitives_base_defaults.keys():
                element_code: str = self.statement_primitive_construct(element)
                elements.append(element_code)
            else:
                assert element.cursor
                # Need to convert element Declaration to TypeDeclaration

                # Start by getting the references using the cursor.
                # Cannot use normal _get_references(element) because
                # element (kind) is a FIELD_DECL inside of the struct.
                refs: list[Declaration] = self.ast._get_type_references_by_cursor(
                    cursor=element.cursor
                )

                type_declaration: Optional[TypeDeclaration] = None
                # Need to find the type declaration for the element in the AST.
                for ref in refs:
                    assert ref.cursor
                    ref_kind: cindex.CursorKind = ref.cursor.kind
                    if (
                        ref_kind.is_declaration()
                        and ref_kind != cindex.CursorKind.FIELD_DECL
                    ):
                        type_declaration = TypeDeclaration.from_cursor(ref.cursor)
                        break

                assert (
                    type_declaration != None
                ), f"Reference for type {element} could not be found"

                # Get decleration in AST
                element_code: str = self.statement_type_construct(type_declaration)
                elements.append(element_code)

        cmd += ",".join(elements) + "}"

        # If this construction should be an assignment call.
        if assign_to != "":
            assign_type: str = d.type_name
            if d.type_name == "":
                assign_type = f"{d.construct_type} {d.name}"

            cmd = f"{assign_type} {assign_to} = {cmd};"

        return cmd

    def statement_function_call(
        self,
        fn: FunctionDeclaration,
        result: Optional[Declaration] = None,
    ) -> str:
        """Calls a function fn, returns to result."""
        raise NotImplementedError()
