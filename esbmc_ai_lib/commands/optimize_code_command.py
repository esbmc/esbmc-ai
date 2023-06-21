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

    def check_function_equivalence(
        self,
        original_source_code: str,
        new_source_code: str,
        function_name: str,
    ) -> bool:
        """TODO Implement function equivalence checking:
        Build source code.
        1. Include the functions as function_orig and function_new
        2. In the main file of the function include a declaration variable of
        nondet_X where X is the type of each parameter that the function
        accepts.
        3. Call each function and equate results.
        """

        # Get list of function types.
        original_ast: ast.ClangAST = ast.ClangAST(
            file_path="",
            source_code=original_source_code,
        )

        new_ast: ast.ClangAST = ast.ClangAST(
            file_path="",
            source_code=new_source_code,
        )

        orig_functions: set[FunctionDeclaration] = set(original_ast.get_fn_decl())
        new_functions: set[FunctionDeclaration] = set(new_ast.get_fn_decl())

        if orig_functions != new_functions:
            return False

        print("WARNING: MOCK FUNCTION DOES NOT VERIFY")
        print("TODO...")

        return True

    def execute(
        self, file_path: str, source_code: str, function_names: list[str]
    ) -> None:
        clang_ast: ast.ClangAST = ast.ClangAST(
            file_path=file_path,
            source_code=source_code,
        )

        all_functions: list[FunctionDeclaration] = clang_ast.get_fn_decl()
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

        new_source_code: str = source_code
        max_retries: int = 10
        for function in function_names:
            for attempt in range(max_retries):
                print(f"Optimizing function: {function}")
                response: ChatResponse = chat.optimize_function(
                    source_code=new_source_code,
                    function_name=function,
                )

                equal: bool = self.check_function_equivalence(
                    original_source_code=source_code,
                    new_source_code=new_source_code,
                    function_name=function,
                )

                if equal:
                    new_source_code = response.message
                    break
                else:
                    print("Failed attempt", attempt)

        print("\nOptimizations Completed:\n")
        print(new_source_code)
        print()
