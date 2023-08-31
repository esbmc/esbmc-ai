# Author: Yiannis Charalambous 2023

import esbmc_ai_lib.frontend.ast as ast
from esbmc_ai_lib.frontend.ast import ClangAST, FunctionDeclaration, Declaration
from esbmc_ai_lib.frontend.ast_decl import (
    InclusionDirective,
    TypeDeclaration,
    TypedefDeclaration,
)


def test_get_source_code() -> None:
    fn_atomic_acquire = """void __VERIFIER_atomic_acquire(void)
{
    __VERIFIER_assume(a == 0);
    a = 1;
}"""
    fn_c = """void *c(void *arg)
{
    ;
    __VERIFIER_atomic_acquire();
    b = 1;
    return NULL;
}"""
    fn_main = """int main()
{
    pthread_create(&d, 0, c, 0);
    __VERIFIER_atomic_acquire();
    if (!b)
        assert(0);
    return 0;
}"""
    source_code = f"""#include <pthread.h>
#include <assert.h>

int a, b;
{fn_atomic_acquire}
{fn_c}
pthread_t d;
{fn_main}"""
    ast: ClangAST = ClangAST("test.c", source_code=source_code)

    fns: list[FunctionDeclaration] = ast.get_fn_decl()

    assert ast.get_source_code(fns[0]) == fn_atomic_acquire
    assert ast.get_source_code(fns[1]) == fn_c
    assert ast.get_source_code(fns[2]) == fn_main


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
}"""
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


def test_get_type_decl() -> None:
    source_code = """struct linear
{
    int value;
};

typedef struct
{
    int x;
    int y;
} Point;

typedef enum Types
{
    ONE,
    TWO,
    THREE
} Typest;

enum Types e = ONE;

Typest f = TWO;

union Combines
{
    int a;
    int b;
    int c;
};

typedef union Combines CombinesTypeDef;

enum extra { A, B, C};

typedef enum extra ExtraEnum;"""

    answers: list = [
        TypeDeclaration(
            name="linear",
            type_name="",
            construct_type=TypeDeclaration.ConstructTypes.STRUCT,
            elements=[Declaration("value", "int")],
        ),
        TypeDeclaration(
            name="",
            type_name="",
            construct_type=TypeDeclaration.ConstructTypes.STRUCT,
            elements=[Declaration("x", "int"), Declaration("y", "int")],
        ),
        TypeDeclaration(
            name="Types",
            type_name="",
            construct_type=TypeDeclaration.ConstructTypes.ENUM,
            elements=[
                Declaration("ONE", "int"),
                Declaration("TWO", "int"),
                Declaration("THREE", "int"),
            ],
        ),
        TypeDeclaration(
            name="Combines",
            type_name="",
            construct_type=TypeDeclaration.ConstructTypes.UNION,
            elements=[
                Declaration(name="a", type_name="int"),
                Declaration(name="b", type_name="int"),
                Declaration(name="c", type_name="int"),
            ],
        ),
    ]

    ast: ClangAST = ClangAST("test.c", source_code)
    types: list[TypeDeclaration] = ast.get_type_decl()

    for type_declaration, answer in zip(types, answers):
        assert (
            type_declaration == answer
        ), f'not equal: "{type_declaration}" and "{answer}"'


def test_get_typedef_decl() -> None:
    source_code = """struct linear
{
    int value;
};

typedef struct linear LinearTypeDef;

typedef struct
{
    int x;
    int y;
} Point;

union Combines
{
    int a;
    int b;
    int c;
};

typedef union Combines CombinesTypeDef;"""

    answers: list[TypedefDeclaration] = [
        TypedefDeclaration(
            name="LinearTypeDef",
            type_name="",
            underlying_type=TypeDeclaration(
                name="linear",
                type_name="",
                construct_type=TypeDeclaration.ConstructTypes.STRUCT,
                elements=[Declaration("value", "int")],
            ),
        ),
        TypedefDeclaration(
            name="Point",
            type_name="",
            underlying_type=TypeDeclaration(
                name="",
                type_name="",
                construct_type=TypeDeclaration.ConstructTypes.STRUCT,
                elements=[Declaration("x", "int"), Declaration("y", "int")],
            ),
        ),
        TypedefDeclaration(
            name="CombinesTypeDef",
            type_name="",
            underlying_type=TypeDeclaration(
                name="Combines",
                type_name="",
                construct_type=TypeDeclaration.ConstructTypes.UNION,
                elements=[
                    Declaration(name="a", type_name="int"),
                    Declaration(name="b", type_name="int"),
                    Declaration(name="c", type_name="int"),
                ],
            ),
        ),
    ]

    ast: ClangAST = ClangAST("test.c", source_code)
    typedefs: list[TypedefDeclaration] = ast.get_typedef_decl()

    print()

    for typedef, answer in zip(typedefs, answers):
        assert typedef == answer, f'not equal: "{typedef}" and "{answer}"'


def test_get_variable_decl() -> None:
    source_code: str = """int a, b;
char* c;
char d[10];
int e = 100;
float f = 0.1f;"""

    ast: ClangAST = ClangAST("test.c", source_code)
    vars: list[str] = [str(var) for var in ast.get_variable_decl()]

    assert vars[0] == "a:int"
    assert vars[1] == "b:int"
    assert vars[2] == "c:char *"
    assert vars[3] == "d:char[10]"
    assert vars[4] == "e:int"
    assert vars[5] == "f:float"


def test_get_include_directives() -> None:
    source_code: str = """#include "assert.h"
#include <stdlib.h>"""

    ast: ClangAST = ClangAST(file_path="test.c", source_code=source_code)
    includes: list[InclusionDirective] = ast.get_include_directives()

    assert (
        len(includes) == 2
    ), "Could not detect all includes. Make sure that libc is installed (or gcc)."

    includes[0].path = "assert.h"
    includes[1].path = "stdlib.h"

    assert str(includes[0]) == '#include "assert.h"'
    assert str(includes[1]) == '#include "stdlib.h"'


def test_get_references_variables() -> None:
    source_code: str = """int a, b;
int main(int argc, char**argv) {
    a = 1;
    b = 2;
    return 0;
}"""

    ast: ClangAST = ClangAST("test.c", source_code)
    variables: list[Declaration] = ast.get_variable_decl()

    answers: list = [
        {
            "name": "a",
            "type_name": "int",
        },
        {
            "name": "b",
            "type_name": "int",
        },
    ]

    for variable, answer in zip(variables, answers):
        assert variable.name == answer["name"]
        assert variable.type_name == answer["type_name"]


# TODO
# def test_get_references_functions() -> None:
#     pass

# TODO
# def test_get_references_types() -> None:
#     pass


def test_rename_function() -> None:
    source_code: str = """int a, b;

int add() {
    return a + b;
}

int sub() {
    return a - b;
}

int main(int argc, char**argv) {
    a = 1;
    b = 2;
    add();
    sub();
    add();
    return 0;
}"""

    ast: ClangAST = ClangAST("test.c", source_code)
    functions: list[FunctionDeclaration] = ast.get_fn_decl()


# TODO
# def test_rename_type() -> None:
#     pass


def test_rename_typedef() -> None:
    source_code: str = """
struct Point_t
{
    int x, y;
};

typedef struct Point_t Point;

typedef struct {
    float radius;
} Circle;"""

    answer: str = """
struct Point_t
{
    int x, y;
};

typedef struct Point_t_renamed Point;

typedef struct {
    float radius;
} Circle_renamed;"""

    ast: ClangAST = ClangAST("test.c", source_code)
    typedefs: list[TypedefDeclaration] = ast.get_typedef_decl()

    print("Found total typedefs:", len(typedefs))

    for typedef in typedefs:
        ast.rename_declaration(typedef, typedef.name + "_renamed")

    assert ast.source_code == answer


def test_rename_global_variable() -> None:
    source_code: str = """#include <assert.h>

struct Point_t
{
    int x, y;
};

typedef struct Point_t Point;

int a, b = 0;

int add_point(struct Point_t p)
{
    return p.x + p.y;
}

int add(int val1, int val2)
{
    return val1 + val2;
}

int main()
{
    a = add(2, 2);
    b = add(6, 0);

    struct Point_t p1 = {a, b};
    a = add_point(p1);

    assert(a == 9);
}"""

    answer: str = """#include <assert.h>

struct Point_t
{
    int x, y;
};

typedef struct Point_t Point;

int a_renamed, b_renamed = 0;

int add_point(struct Point_t p)
{
    return p.x + p.y;
}

int add(int val1, int val2)
{
    return val1 + val2;
}

int main()
{
    a_renamed = add(2, 2);
    b_renamed = add(6, 0);

    struct Point_t p1 = {a_renamed, b_renamed};
    a_renamed = add_point(p1);

    assert(a_renamed == 9);
}"""

    ast: ClangAST = ClangAST("test.c", source_code)
    variables: list[Declaration] = ast.get_variable_decl()

    for variable in variables:
        ast.rename_declaration(variable, variable.name + "_renamed")

    assert ast.source_code == answer
