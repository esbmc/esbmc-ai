# Author: Yiannis Charalambous

verbose: int = 0


def set_verbose(level: int) -> None:
    global verbose
    verbose = level


def printv(m) -> None:
    if verbose > 0:
        print(m)
