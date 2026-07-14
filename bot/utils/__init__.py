from bot.utils.id import generate_id
from bot.utils.embeds import error_embed, generate_author_text
from .queue_paginator import QueuedSuggestionsPaginator
from .voter_paginator import ViewVotersPaginator
from .errors import HandleClientHTTPResponse, should_handle_error
from .otel import start_error_span, get_trace_id
from .users import fetch_user_avatar
from .cv2 import insert_user_segment

__all__ = [
    "HandleClientHTTPResponse",
    "QueuedSuggestionsPaginator",
    "ViewVotersPaginator",
    "error_embed",
    "fetch_user_avatar",
    "generate_author_text",
    "generate_id",
    "get_trace_id",
    "insert_user_segment",
    "should_handle_error",
    "start_error_span",
]
