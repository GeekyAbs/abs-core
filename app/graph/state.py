from typing import TypedDict


class ChatState(TypedDict):
    session_id: str
    user_input: str
    retrieved: list[dict]
    reply: str
    blocked: bool
    block_reason: str