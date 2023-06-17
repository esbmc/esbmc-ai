# Author: Yiannis Charalambous

from .chat_command import ChatCommand
from .. import config
from ..base_chat_interface import ChatResponse
from ..optimize_code import OptimizeCode
from ..frontend import ast
from ..frontend.ast import FunctionDeclaration


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

        all_functions: list[FunctionDeclaration] = clang_ast.get_function_declarations()
        all_function_names: list[str] = [fn.name for fn in all_functions]

        # If specific function names to optimize have been specified, then
        # check that they exist.
        if len(function_names) > 0:
            for function_name in function_names:
                if function_name not in all_function_names:
                    print(f"Error: {function_name} is not defined...")
                    exit(1)
        else:
            function_names = all_function_names.copy()

        print(f"Optimizing the following functions: {function_names}\n")

        chat: OptimizeCode = OptimizeCode(
            system_messages=config.chat_prompt_optimize_code.system_messages,
            initial_message=config.chat_prompt_optimize_code.initial_prompt,
            ai_model=config.ai_model,
            temperature=config.chat_prompt_optimize_code.temperature,
        )

        for function in function_names:
            print(f"Optimizing function: {function}")
            response: ChatResponse = chat.optimize_function(
                source_code=source_code,
                function_name=function,
            )

            # TODO Implement function equivalence checking.

            source_code = response.message

        print("\nOptimizations Completed:\n")
        print(source_code)
        print()
