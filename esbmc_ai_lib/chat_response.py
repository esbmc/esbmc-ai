# Author: Yiannis Charalambous

from typing import NamedTuple

# API returned complete model output
FINISH_REASON_STOP: str = "stop"
# Incomplete model output due to max_tokens parameter or token limit
FINISH_REASON_LENGTH: str = "length"
# Omitted content due to a flag from our content filters
FINISH_REASON_CONTENT_FILTER: str = "content_filter"
# API response still in progress or incomplete
FINISH_REASON_NULL: str = "null"


class ChatResponse(NamedTuple):
    base_message: object = None
    finish_reason: str = FINISH_REASON_NULL
    role: str = ""
    message: str = ""
    total_tokens: int = 0
