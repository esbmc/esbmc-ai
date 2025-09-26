# Author: Yiannis Charalambous

from enum import Enum


class LogCategories(Enum):
    NONE = "NONE"
    ALL = "ALL"
    SYSTEM = "ESBMC_AI"
    VERIFIER = "VERIFIER"
    COMMAND = "COMMAND"
    CONFIG = "CONFIG"
    CHAT = "CHAT"
