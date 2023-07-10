# Author: Yiannis Charalambous

from os.path import dirname, join as path_join
from typing import Optional

import clang.native
import clang.cindex as cindex
from clang.cindex import Config

from .ast_decl import *

# Connect the Python API of Clang to the libclang.so file bundled in the libclang PyPI package.
Config.library_file = path_join(
    dirname(clang.native.__file__),
    "libclang.so",
)


class ClangAST(object):
    file_path: str
    source_code: str
    index: cindex.Index
    tu: cindex.TranslationUnit
    root: cindex.Cursor

    def __init__(
        self,
        file_path: str,
        source_code: Optional[str] = None,
    ) -> None:
        super().__init__()

        self.file_path = file_path
        self.index = cindex.Index.create()

        if source_code == "":
            raise ValueError("file_path provided cannot be empty string...")

        if source_code is None:
            # Load from file
            self.tu = self.index.parse(path=file_path)
        else:
            self.source_code = source_code
            # Load from string
            self.tu = self.index.parse(
                path=file_path,
                unsaved_files=[(file_path, source_code)],
            )
        self.root = self.tu.cursor

    def get_source_code(self, declaration: Declaration) -> str:
        if declaration.cursor is None:
            raise ValueError("")
        node: cindex.Cursor = declaration.cursor
        loc: cindex.SourceRange = node.extent
        start: cindex.SourceLocation = loc.start
        end: cindex.SourceLocation = loc.end
        return self.source_code[start.offset : end.offset]

    def get_fn_decl(self) -> list[FunctionDeclaration]:
        """Get function declaration list."""
        functions: list[FunctionDeclaration] = []
        node: cindex.Cursor
        for node in self.root.get_children():
            kind: cindex.CursorKind = node.kind
            # StorageClass.NONE indicates that the declaration is inside the file.
            if (
                kind.is_declaration()
                and node.storage_class == cindex.StorageClass.NONE
                and kind == cindex.CursorKind.FUNCTION_DECL
            ):
                functions.append(FunctionDeclaration.from_cursor(node))
        return functions

    def get_type_decl(self) -> list[TypeDeclaration]:
        typedefs: list[TypeDeclaration] = []
        node: cindex.Cursor
        for node in self.root.get_children():
            kind: cindex.CursorKind = node.kind
            if (
                kind.is_declaration()
                # NOTE StorageClass.INVALID for some reason is what works here instead of NONE.
                # This may be a bug that's fixed in future versions of libclang.
                and node.storage_class == cindex.StorageClass.INVALID
                and (
                    kind == cindex.CursorKind.STRUCT_DECL
                    or kind == cindex.CursorKind.UNION_DECL
                    or kind == cindex.CursorKind.ENUM_DECL
                    or kind == cindex.CursorKind.TYPEDEF_DECL
                )
            ):
                typedefs.append(TypeDeclaration.from_cursor(node))

        return typedefs

    def get_variable_decl(self) -> list[Declaration]:
        variables: list[Declaration] = []
        node: cindex.Cursor
        for node in self.root.get_children():
            kind: cindex.CursorKind = node.kind
            if (
                kind.is_declaration()
                and node.storage_class == cindex.StorageClass.NONE
                and kind == cindex.CursorKind.VAR_DECL
            ):
                variables.append(Declaration.from_cursor(node))
        return variables

    def get_include_directives(self) -> list[InclusionDirective]:
        includes: list[InclusionDirective] = []
        include: cindex.FileInclusion
        for include in self.tu.get_includes():
            if include.depth == 1:
                includes.append(InclusionDirective(path=str(include.include)))
        return includes

    def get_all_decl(self) -> list[Declaration]:
        """Returns all local declarations."""
        declarations: list[Declaration] = []
        declarations.extend(self.get_fn_decl())
        declarations.extend(self.get_type_decl())
        declarations.extend(self.get_variable_decl())
        declarations.extend(self.get_enum_decl())
        # TODO add more...
        return declarations
