from typing import Literal, Optional

from pydantic import BaseModel


class SourceReference(BaseModel):
    filename: str
    page_content: str
    chunk_index: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    session_id: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    content: str
    metadata: dict
    score: Optional[float] = None


class SearchResult(BaseModel):
    results: list[SearchHit]


class WsIncoming(BaseModel):
    type: Literal["message", "ping"]
    message: str = ""
    session_id: Optional[str] = None


class WsOutgoing(BaseModel):
    type: Literal["token", "sources", "done", "error", "pong"]
    content: str = ""
    sources: list[SourceReference] = []
