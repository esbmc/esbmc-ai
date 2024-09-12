# Author: Yiannis Charalambous

"""API Key Collection definition."""

from typing import NamedTuple, Optional


class APIKeyCollection(NamedTuple):
    """Class that is used to pass keys to AIModels."""

    openai: Optional[str]
