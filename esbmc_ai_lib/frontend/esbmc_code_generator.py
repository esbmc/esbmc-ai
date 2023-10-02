# Author: Yiannis Charalambous

from typing import Callable, Optional

import clang.cindex as cindex

from .ast import ClangAST
from .ast_decl import Declaration, TypeDeclaration, FunctionDeclaration
from .c_types import is_primitive_type


"""Note about how `assign_to` and `init` work:
* `assign_to: Optional[str] = None`: By default the result will not be a statement,
but will generate a value. By assigning "", a statement will be returned. By assigning
a string name, a value will be assigned to that string name.
* `init: bool = False`: This does not matter, unless `assign_to != None` and has a value other
than "", will initialize the variable by appending the type information before the name."""


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
        self,
        d: Declaration,
        assign_to: Optional[str] = None,
        init: bool = False,
    ) -> str:
        """Returns the primitive construction of a variable/value. Will be
        __VERIFIER_nondet_X(). The list of available ESBMC functions is taken
        from https://github.com/esbmc/esbmc/blob/master/src/clang-c-frontend/clang_c_language.cpp
        """

        value: str = ESBMCCodeGenerator._primitives_base_defaults[d.type_name]

        if assign_to == None:
            return value
        else:
            if assign_to == "":
                return value + ";"
            else:
                return (d.type_name + " " if init else "") + f"{assign_to} = {value};"

    def statement_type_construct(
        self,
        d: TypeDeclaration,
        assign_to: Optional[str] = None,
        init: bool = False,
        primitive_assignment_fn: Optional[Callable[[Declaration], str]] = None,
    ) -> str:
        """Constructs a statement to  that is represented by decleration d."""
        assert d.cursor

        cmd: str

        # Check if primitive type and return nondet value.
        if len(list(d.cursor.get_children())) == 0:
            return self.statement_primitive_construct(d)

        cmd = "(" + (d.type_name if d.is_typedef() else f"struct {d.name}") + "){"

        # Loop through each element of the data type.
        elements: list[str] = []
        for element in d.elements:
            # Check if element is a primitive type. If not, it will need to be
            # further broken.
            if is_primitive_type(element):
                element_code: str
                # Call primitive assignment function if available in order to
                # assign a value. If not, then assign primitive using default
                # way.
                if primitive_assignment_fn != None:
                    element_code = primitive_assignment_fn(element)
                else:
                    element_code = self.statement_primitive_construct(element)
                elements.append(element_code)
            else:
                assert element.cursor
                # Need to convert element Declaration to TypeDeclaration

                type_declaration: Optional[
                    TypeDeclaration
                ] = self.ast._get_type_declaration_from_cursor(element.cursor)

                assert (
                    type_declaration != None
                ), f"Reference for type {element} could not be found"

                # Get decleration in AST
                element_code: str = self.statement_type_construct(type_declaration)
                elements.append(element_code)

        cmd += ",".join(elements) + "}"

        # If this construction should be an assignment call.
        if assign_to != None:
            if assign_to == "":
                cmd = cmd + ";"
            elif d.type_name != "void":
                # Check if assignment variable should be initialized.
                if init:
                    assign_type: str = d.type_name
                    if d.type_name == "":
                        assign_type = f"{d.construct_type} {d.name}"

                    cmd = f"{assign_type} {assign_to} = {cmd};"
                else:
                    cmd = f"{assign_to} = {cmd};"

        return cmd

    def statement_function_call(
        self,
        fn: FunctionDeclaration,
        params: Optional[list[str]] = None,
        assign_to: Optional[str] = None,
        init: bool = False,
    ) -> str:
        """Calls a function fn, returns to result."""

        assert fn.cursor

        cmd: str = fn.name + "("

        # Parameter generation
        if params != None:
            # Given parameters
            cmd += ", ".join(params) + ")"
        else:
            # Walk through arguments
            arg_cmds: list[str] = []
            for arg in fn.args:
                assert arg.cursor

                # Check if primitive type.
                if is_primitive_type(arg):
                    arg_cmds.append(self.statement_primitive_construct(arg))
                else:
                    # Current cursor kind is CursorKind.PARAM_DECL, need to
                    # get underlying type.
                    underlying_type: cindex.Type = arg.cursor.type.get_canonical()
                    underlying_cursor: cindex.Cursor = underlying_type.get_declaration()

                    arg_type: Optional[
                        TypeDeclaration
                    ] = self.ast._get_type_declaration_from_cursor(underlying_cursor)

                    if arg_type is None:
                        raise ValueError(
                            "Statement function call: Could not find declaration for"
                            + arg.name
                            + " "
                            + arg.type_name
                        )
                    arg_cmds.append(self.statement_type_construct(d=arg_type))

            cmd += ", ".join(arg_cmds) + ")"

        # If this construction should be an assignment call.
        if assign_to != None:
            if assign_to == "":
                cmd = cmd + ";"
            elif fn.type_name != "void":
                if init:
                    assign_type: str = fn.type_name
                    cmd = f"{assign_type} {assign_to} = {cmd};"
                else:
                    cmd = f"{assign_to} = {cmd};"

        return cmd
