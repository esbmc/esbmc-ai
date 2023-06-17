# Author: Yiannis Charalambous

from os.path import dirname, join as path_join
from typing import NamedTuple

import clang.native
import clang.cindex as cindex
from clang.cindex import Config

# Connect the Python API of Clang to the libclang.so file bundled in the libclang PyPI package.
Config.library_file = path_join(
    dirname(clang.native.__file__),
    "libclang.so",
)


class Declaration(NamedTuple):
    name: str
    type: str


class FunctionDeclaration(NamedTuple):
    name: str
    type: str
    args: list[Declaration]


class ClangAST(object):
    file_path: str
    source_code: str
    index: cindex.Index
    tu: cindex.TranslationUnit
    root: cindex.Cursor

    def __init__(self, file_path: str = "", source_code: str = "") -> None:
        super().__init__()

        self.file_path = file_path
        self.index = cindex.Index.create()

        if source_code == "":
            # Load from file
            self.tu = self.index.parse(path=file_path)
        else:
            # Load from string
            self.tu = self.index.parse(
                path=file_path,
                unsaved_files=[(file_path, source_code)],
            )
        self.root = self.tu.cursor

    def get_function_declarations(self) -> list[FunctionDeclaration]:
        functions: list[FunctionDeclaration] = []
        node: cindex.Cursor
        for node in self.root.get_children():
            kind: cindex.CursorKind = node.kind
            if (
                kind.is_declaration()
                and node.storage_class == cindex.StorageClass.NONE
                and kind == cindex.CursorKind.FUNCTION_DECL
            ):
                # Get function parameters.
                arg: cindex.Cursor
                function_params: list[Declaration] = []
                for arg in node.get_arguments():
                    param_type: cindex.Type = arg.type
                    param: Declaration = Declaration(
                        name=arg.spelling,
                        type=param_type.spelling,
                    )
                    function_params.append(param)

                function_declaration: FunctionDeclaration = FunctionDeclaration(
                    name=node.spelling,
                    type=node.type.get_result().spelling,
                    args=function_params,
                )
                functions.append(function_declaration)
        return functions
