# Author: Yiannis Charalambous


from typing_extensions import override


class Declaration(object):
    name: str
    type_name: str

    def __init__(self, name: str, type_name: str) -> None:
        self.name = name
        self.type_name = type_name

    @override
    def __hash__(self) -> int:
        return self.name.__hash__() + self.type_name.__hash__()


class FunctionDeclaration(Declaration):
    args: list[Declaration] = []

    def __init__(self, name: str, type_name: str, args: list[Declaration]) -> None:
        super().__init__(name, type_name)
        self.args = args

    @override
    def __hash__(self) -> int:
        hash_result: int = 0
        for arg in self.args:
            hash_result += arg.__hash__()
        return super().__hash__() + hash_result
