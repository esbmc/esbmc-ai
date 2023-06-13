# Author: Yiannis Charalambous

from os.path import dirname, join as path_join

import clang.native
import clang.cindex
from clang.cindex import Config

# Connect the Python API of Clang to the libclang.so file bundled in the libclang PyPI package.
Config.library_file = path_join(
    dirname(clang.native.__file__),
    "libclang.so",
)
