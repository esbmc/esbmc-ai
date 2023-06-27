# Author: Yiannis Charalambous


from typing import NamedTuple


class APIKeyCollection(NamedTuple):
    openai: str = ""
    huggingface: str = ""
