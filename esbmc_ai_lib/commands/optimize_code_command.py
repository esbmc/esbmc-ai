# Author: Yiannis Charalambous

from .. import config
from .chat_command import ChatCommand
from ..frontend import ast


class OptimizeCodeCommand(ChatCommand):
    def __init__(self) -> None:
        super().__init__(
            command_name="optimize-code",
            help_message="Optimizes the code of a specific function or the entire file if a function is not specified. Usage: optimize-code [function_name]",
        )

    def execute(
        self, file_path: str, source_code: str, function_names: list[str]
    ) -> None:
        clang_ast: ast.ClangAST = ast.ClangAST(
            file_path=file_path, source_code=source_code
        )

        all_functions: list[str] = clang_ast.get_function_declarations()

        if len(function_names) > 0:
            # Loop through and verify every function is valid.
            for function_name in function_names:
                if function_name not in all_functions:
                    print(f"Error: {function_name} is not defined...")
                    exit(1)
        else:
            function_names = all_functions.copy()

        print(f"Optimizing the following functions: {function_names}")

        for function in function_names:
            print(f"\nOptimizing function: {function}")
            print("TODO")
