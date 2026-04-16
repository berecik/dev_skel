import time
import uuid
from collections import defaultdict
from typing import Protocol

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class ConversationStore(Protocol):
    def get_messages(self, session_id: str) -> list[BaseMessage]: ...
    def add_user_message(self, session_id: str, content: str) -> None: ...
    def add_ai_message(self, session_id: str, content: str) -> None: ...
    def clear(self, session_id: str) -> None: ...


class InMemoryHistory:
    def __init__(self, max_turns: int = 10, ttl_seconds: int = 3600):
        self._store: dict[str, list[BaseMessage]] = defaultdict(list)
        self._timestamps: dict[str, float] = {}
        self._max_turns = max_turns
        self._ttl = ttl_seconds

    def _evict_stale(self) -> None:
        now = time.time()
        stale = [k for k, ts in self._timestamps.items() if now - ts > self._ttl]
        for k in stale:
            del self._store[k]
            del self._timestamps[k]

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        self._evict_stale()
        return list(self._store.get(session_id, []))

    def add_user_message(self, session_id: str, content: str) -> None:
        self._timestamps[session_id] = time.time()
        msgs = self._store[session_id]
        msgs.append(HumanMessage(content=content))
        if len(msgs) > self._max_turns * 2:
            self._store[session_id] = msgs[-(self._max_turns * 2):]

    def add_ai_message(self, session_id: str, content: str) -> None:
        self._timestamps[session_id] = time.time()
        self._store[session_id].append(AIMessage(content=content))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._timestamps.pop(session_id, None)


_history_store: InMemoryHistory | None = None


def get_history_store(max_turns: int = 10) -> InMemoryHistory:
    global _history_store
    if _history_store is None:
        _history_store = InMemoryHistory(max_turns=max_turns)
    return _history_store


def new_session_id() -> str:
    return uuid.uuid4().hex[:16]
