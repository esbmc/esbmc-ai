Optimize Code Mode (OCM) is an experimental new mode added into ESBMC-AI that optimizes functions into smaller, more efficient forms. The mode attempts to optimize the function as best as possible without changing the layout of the code, so ideally, it is a drop-in optimizer for C/C++ functions. OCM relies on the ClangAST backend developed for interacting with source code in order to ensure that the optimized code is partially equivalent with the original source code. OCM can be summarized as the following steps:

1. Initialize a ClangAST instance for the old source code.
2. Get all functions of the old source code.
3. Split the task into each function, so each function will be optimized separately.
4. For each function to optimize:
    1. Optimize the function.
    2. Initialize a ClangAST instance for the new source code.
    3. Compare function signatures to ensure that they are equal. That is, the optimized new function should have the exact same signature as the old function signature.
    4. Perform partial equivalence checking to ensure that the original and optimized functions are partially equivalent.
    5. If equivalent, then perform step _i_ for the next function but with the optimized source code, such that the source code gets optimized as each function is optimized. If not, then retry from step _i_ for the same function without changing the original source code.
5. Once all functions have been optimized, the whole source code should be optimized, the results are returned.

## Partial Equivalence Checking

The partial equivalence checking process uses ESBMC as the backend, along with a [function equivalence script](https://github.com/Yiannis128/esbmc-ai/blob/master/scripts/function_equivalence.c). The function equivalence script is responsible for programming ESBMC to check for the partial equivalence of the original and optimized functions. The term “partial equivalence” is used because it refers to the fact that checking for full equivalence in the input/output space is undecidable with certain programs (loops). The equivalence script is populated by the old and new source code (original source code and optimized source code, respectively). In order to not have any identifier and type clashes in the code, any declarations of types and identifiers in the two source code files are renamed, using the ClangAST backend. The terms "_\_old_" and "_\_new_" appended at the end. This change makes the code able to be included in a single C source code file that compiles.

The following fields are inserted into the equivalence script in order to check the partial equivalence of the optimized function:

* `function_old`: The original source code is inserted.
* `function_new`: The new optimized source code is inserted.
* `parameters_list`: Using ClangAST, the parameters for the functions are initialized and placed here. The same `__VERIFIER_nondet_X` is used for both function by assigning it to a common variable first.
* `function_call_old` and `function_call_new`: The old function and new function invocation code is inserted here, respectively. The variables from `parameter_list` are also inserted. The results from the functions are inserted into a new variable.
* `function_assert_old` and `function_assert_new`: The results from the functions are compared in this assert statement. Due to the nature of `__VERIFIER_nondet_X`, the entire input space of the function is explored, this means that if an input doesn't match an output, ESBMC will not successfully verify the source code.

# Configuration Options

The mode can be configured with the following options.

## Array expansion

`array_expansion` defines the continuous memory that arrays and pointers should be initialized to. The current system is very limited, in the future, work needs to be done to resolve the limitations of function parameter pointers being only continuous memory.

## Init Max Depth

`init_max_depth` defines the max depth that structs will be initialized into. After a pointer is encountered beyond depth, a `NULL` value will be assigned.

## Partial Equivalence Check Mode

`partial_equivalence_check` defines the mode that the resulting value of the optimized and original result are checked. The following options are available:
* `basic`: Performs a basic equality check of the original and optimized result – `assert(result_old == result_new);`. This method is basic in its nature, however, it is the fastest method.
* `deep`: Will traverse the original and optimized result depth first and perform equality checks. This ensures that the entire struct is checked. When a pointer is encountered, it will dereference it and explore its elements. If it is an array, then the array elements will be explored depth first as well. The depth of initialization and width of array exploration are defined in the config by the values `init_max_depth` and `array_expansion` respectively.

# Limitations of Partial Equivalence Checking

TBD

# Unsupported C/C++ Language Features

Currently, the following C/C++ language features are not supported by Optimize Code Mode. The list might be incomplete.

* Typedefs: They are not renamed.
* No C++ Features supported: Classes, Templates, etc.