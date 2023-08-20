# Author: Yiannis Charalambous


from esbmc_ai_lib.frontend.ast import ClangAST
from esbmc_ai_lib.frontend.ast_decl import Declaration, TypeDeclaration
from esbmc_ai_lib.frontend.esbmc_code_generator import ESBMCCodeGenerator


def test_statement_type_construct() -> None:
    source_code: str = """struct abc {
    int a, b;
    char c;
};

struct abcd {
    struct abc abc_instance;
    long long int d;
};"""

    answers_inline: list[str] = [
        "(struct abc){__VERIFIER_nondet_int(),__VERIFIER_nondet_int(),__VERIFIER_nondet_char()}",
        "(struct abcd){(struct abc){__VERIFIER_nondet_int(),__VERIFIER_nondet_int(),__VERIFIER_nondet_char()},__VERIFIER_nondet_long()}",
    ]

    assign_to_vars: list[str] = [
        "abc_instance",
        "abcd_instance",
    ]

    answers: list[str] = [
        f"{assign_to_vars[0]} = {answers_inline[0]};",
        f"{assign_to_vars[1]} = {answers_inline[1]};",
    ]

    answers_init: list[str] = [
        f"struct abc {assign_to_vars[0]} = {answers_inline[0]};",
        f"struct abcd {assign_to_vars[1]} = {answers_inline[1]};",
    ]

    ast: ClangAST = ClangAST("test.c", source_code)
    code_gen: ESBMCCodeGenerator = ESBMCCodeGenerator(ast)

    # Get functions and test
    types: list[TypeDeclaration] = ast.get_type_decl()

    # Inline tests
    for idx, t in enumerate(types):
        result: str = code_gen.statement_type_construct(d=t)
        assert result == answers_inline[idx]

    # Assignment tests with init
    for idx, t in enumerate(types):
        result: str = code_gen.statement_type_construct(
            d=t,
            assign_to=assign_to_vars[idx],
            init=True,
        )
        assert result == answers_init[idx]

    # Assignment tests
    for idx, t in enumerate(types):
        result: str = code_gen.statement_type_construct(
            d=t,
            assign_to=assign_to_vars[idx],
            init=False,
        )
        assert result == answers[idx]

    # Test primitive assignment.
    type_checks: list[str] = ["int", "int", "char", "long long"]

    def primitive_assignment_fn_test(d: Declaration) -> str:
        assert d.type_name == type_checks.pop(0)
        return code_gen.statement_primitive_construct(d)

    for t in types:
        code_gen.statement_type_construct(
            d=t,
            primitive_assignment_fn=primitive_assignment_fn_test,
        )


def test_function_construct() -> None:
    source_code: str = """typedef int number;
int add(int a, int b) {
    return a + b;
}
number add_number(number a, number b) {
    return a + b;
}
void do_nothing() {}
typedef struct {
    int a;
    int b;
} col;
col create_col(number a, number b) {
    return (col){(int)a, (int)b};
}
"""

    answer_not_assign: list[str] = [
        "add(__VERIFIER_nondet_int(), __VERIFIER_nondet_int())",
        "add_number(__VERIFIER_nondet_int(), __VERIFIER_nondet_int())",
        "do_nothing()",
        "create_col(__VERIFIER_nondet_int(), __VERIFIER_nondet_int())",
    ]

    assign_to_name: str = "res"

    answer_assign_init: list[str] = [
        f"int {assign_to_name} = {answer_not_assign[0]};",
        f"number {assign_to_name} = {answer_not_assign[1]};",
        answer_not_assign[2] + ";",
        f"col {assign_to_name} = {answer_not_assign[3]};",
    ]

    ast: ClangAST = ClangAST("test.c", source_code)
    gen: ESBMCCodeGenerator = ESBMCCodeGenerator(ast)

    fns = ast.get_fn_decl()

    # Don't assign
    for idx, fn in enumerate(fns):
        result: str = gen.statement_function_call(fn=fn)
        assert result == answer_not_assign[idx]

    # Assign to
    for idx, fn in enumerate(fns):
        result: str = gen.statement_function_call(fn=fn, assign_to=assign_to_name)
        if fn.type_name != "void":
            assert result == assign_to_name + " = " + answer_not_assign[idx] + ";"
        else:
            assert answer_not_assign[idx] + ";"

    # Init the result
    for idx, fn in enumerate(fns):
        result: str = gen.statement_function_call(
            fn=fn,
            assign_to="" if fn.type_name == "void" else assign_to_name,
            init=True,
        )
        assert result == answer_assign_init[idx]
