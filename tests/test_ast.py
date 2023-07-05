# Author: Yiannis Charalambous 2023

import pytest

import esbmc_ai_lib.frontend.ast as ast
from esbmc_ai_lib.frontend.ast import FunctionDeclaration, Declaration


def test_ast_functions() -> None:
    file = "test.c"
    source_code = """#include <pthread.h>
#include <assert.h>

int a, b;
void __VERIFIER_atomic_acquire(void)
{
    __VERIFIER_assume(a == 0);
    a = 1;
}
void *c(void *arg)
{
    ;
    __VERIFIER_atomic_acquire();
    b = 1;
    return NULL;
}
pthread_t d;
int main()
{
    pthread_create(&d, 0, c, 0);
    __VERIFIER_atomic_acquire();
    if (!b)
        assert(0);
    return 0;
}
    """
    cast = ast.ClangAST(file_path=file, source_code=source_code)
    functions: list[FunctionDeclaration] = cast.get_fn_decl()
    answer: list[FunctionDeclaration] = [
        FunctionDeclaration(
            name="__VERIFIER_atomic_acquire",
            type_name="void",
            args=[],
        ),
        FunctionDeclaration(
            name="c",
            type_name="void *",
            args=[Declaration(name="arg", type_name="void *")],
        ),
        FunctionDeclaration(
            name="main",
            type_name="int",
            args=[],
        ),
    ]

    assert functions[0] == answer[0]
    assert functions[1] == answer[1]
    assert functions[2] == answer[2]


def test_ast_functions_blank() -> None:
    file = "test.c"
    source_code = """#include <pthread.h>
#include <assert.h>
int a, b;
pthread_t d;
    """

    cast = ast.ClangAST(file_path=file, source_code=source_code)
    functions: list[FunctionDeclaration] = cast.get_fn_decl()
    assert functions == []
