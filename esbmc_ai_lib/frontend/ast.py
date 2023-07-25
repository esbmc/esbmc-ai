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

# NOTE A possible optimization is to traverse children of depth 1.
# A lot of functions traverse all children.


# TODO Adjust storage class checks and add file checks for each get_x_decl

# TODO Make declaration not use Cursor, instead move everything to Declaration
# since inbetween calls, each Cursor can change. (Calls to get_children() will
# yield different Cursors)


class ClangAST(object):
    def __init__(
        self,
        file_path: str,
        source_code: Optional[str] = None,
    ) -> None:
        super().__init__()

        self.index: cindex.Index = cindex.Index.create()

        if file_path == "":
            raise ValueError("file_path provided cannot be empty string...")

        self.file_path: str = file_path

        if source_code is None:
            with open(self.file_path, "r") as file:
                self.source_code: str = file.read()
            # Load from file
            self.tu: cindex.TranslationUnit = self.index.parse(path=self.file_path)
        else:
            self.source_code: str = source_code
            # Load from string
            self.tu: cindex.TranslationUnit = self.index.parse(
                path=self.file_path,
                unsaved_files=[(self.file_path, source_code)],
            )
        self.root: cindex.Cursor = self.tu.cursor

    def _sort_declarations(self, declarations: list[Declaration]) -> list[Declaration]:
        return sorted(
            declarations,
            key=lambda d: d.get_location().offset,
        )

    def _get_type_references_by_cursor(
        self, cursor: cindex.Cursor
    ) -> list[Declaration]:
        name: str = cursor.type.spelling
        # Remove the tag type (first word) which should be struct/enum/union.
        name = name.split(" ", 1)[1]
        d: Declaration = Declaration(
            name=name,
            type_name="",
            cursor=cursor,
        )
        return self._get_references(d)

    def _get_references(self, target: Declaration) -> list[Declaration]:
        """Finds all references to a specific declaration. The returned
        Declarations are not subscribed to the the declarations set."""
        # Refs is a list not a set in order to maintain the order.
        assert target.cursor

        refs: list[Declaration] = []
        added_locs: list[tuple[int, int]] = []

        def traverse_child_node(node: Cursor) -> None:
            kind: cindex.CursorKind = node.kind
            loc: tuple[int, int] = (node.location.line, node.location.column)
            if (
                node.referenced
                and node.referenced.spelling == target.name
                # TODO Evaluate in testing because target.extent might be
                # wrong after repeated renaming.
                # and node.referenced.extent == target.extent
                and (
                    kind.is_expression()
                    or kind.is_declaration()
                    or kind.is_reference()
                    or kind
                    == cindex.CursorKind.FUNCTION_DECL  # TODO This may be removable
                )
                and loc not in added_locs
            ):
                # Make sure not to add a cursor in this location again.
                added_locs.append(loc)
                # Create and add decleration.
                refs.append(target.from_cursor(node))

            for child in node.get_children():
                traverse_child_node(child)

        for child in self.root.get_children():
            traverse_child_node(child)

        return refs

    def rename_declaration(
        self,
        declaration: Declaration,
        new_name: str,
        inplace: bool = True,
    ) -> str:
        """Renames the declaration along with any references to it, returns the new code."""

        # TODO Add edge case: Do not rename for #include calls... Check and
        # rename only in same file as declaration.

        refs: list[Declaration] = self._get_references(declaration)
        source_code: str = self.source_code
        delta: int = len(new_name) - len(declaration.name)
        old_name: str = declaration.name

        # Get sorted list of declarations.
        # TODO ensure that this is needed, as call to _get_references
        # should in theory return the list sorted by position.
        declarations: list[Declaration] = self._sort_declarations(refs)

        # Rename each ref and record all offsets for each declaration after reparsing TU.
        size_offset: int = 0
        for decl in declarations:
            # Check if current declaration is to be renamed or should be adjusted.
            if decl in refs:
                extent: SourceRange = decl.get_extent()
                start_offset: int = extent.start.offset + size_offset
                end_offset: int = extent.end.offset + size_offset
                # Get the reference
                change: str = source_code[start_offset:end_offset]
                # Replace it
                change = change.replace(old_name, new_name, 1)
                # Place replacement in source code
                source_code = (
                    source_code[:start_offset] + change + source_code[end_offset:]
                )

                # Add delta offset so next references are offset by the change in character.
                size_offset += delta

        # Switch to new AST.
        self.tu.reparse(unsaved_files=[(self.file_path, source_code)])
        self.root = self.tu.cursor

        if inplace:
            self.source_code = source_code

        return source_code

    def get_source_code(self, declaration: Declaration) -> str:
        if declaration.cursor is None:
            raise ValueError("Get source code, cursor is null: " + declaration.name)
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
            node_file: str = node.location.file.name
            if (
                kind.is_declaration()
                # NOTE StorageClass.INVALID for some reason is what works here instead of NONE.
                # This may be a bug that's fixed in future versions of libclang.
                and node_file == self.file_path
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
        file_inclusion: cindex.FileInclusion
        for file_inclusion in self.tu.get_includes():
            if file_inclusion.depth == 1:
                includes.append(InclusionDirective(path=str(file_inclusion.include)))

        return includes

    def get_all_decl(self) -> list[Declaration]:
        """Returns all local declarations."""
        declarations: list[Declaration] = []
        declarations.extend(self.get_fn_decl())
        declarations.extend(self.get_type_decl())
        declarations.extend(self.get_variable_decl())
        # TODO Make sure no clones.
        # TODO add more...
        return declarations
