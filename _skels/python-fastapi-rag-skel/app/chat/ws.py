import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.rag.config import get_rag_settings
from app.rag.vectorstore import get_vectorstore
from app.rag.llm import get_llm
from app.rag.chain import build_conversational_chain
from .models import WsIncoming, WsOutgoing, SourceReference
from .history import get_history_store, new_session_id

logger = logging.getLogger(__name__)


def _authenticate_ws(token: str | None) -> bool:
    if not token:
        settings = get_rag_settings()
        return settings.ws_auth != "required"

    try:
        from core.security import decode_token

        decode_token(token)
        return True
    except Exception:
        return False


async def chat_websocket(websocket: WebSocket, token: str | None = None) -> None:
    if not _authenticate_ws(token):
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()

    settings = get_rag_settings()
    store = get_vectorstore(settings)
    llm = get_llm(settings)
    chain = build_conversational_chain(llm, store, top_k=settings.top_k)
    history = get_history_store(max_turns=settings.history_max_turns)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                incoming = WsIncoming.model_validate_json(raw)
            except Exception:
                await websocket.send_text(
                    WsOutgoing(type="error", content="Invalid message format").model_dump_json()
                )
                continue

            if incoming.type == "ping":
                await websocket.send_text(
                    WsOutgoing(type="pong").model_dump_json()
                )
                continue

            session_id = incoming.session_id or new_session_id()
            chat_history = history.get_messages(session_id)

            try:
                full_answer = ""
                context_docs = []

                async for chunk in chain.astream({
                    "input": incoming.message,
                    "chat_history": chat_history,
                }):
                    if "answer" in chunk and chunk["answer"]:
                        full_answer += chunk["answer"]
                        await websocket.send_text(
                            WsOutgoing(type="token", content=chunk["answer"]).model_dump_json()
                        )
                    if "context" in chunk:
                        context_docs = chunk["context"]

                sources = [
                    SourceReference(
                        filename=doc.metadata.get("filename", doc.metadata.get("source", "")),
                        page_content=doc.page_content[:500],
                        chunk_index=doc.metadata.get("chunk_index"),
                    )
                    for doc in context_docs
                ]

                await websocket.send_text(
                    WsOutgoing(type="sources", sources=sources).model_dump_json()
                )
                await websocket.send_text(
                    WsOutgoing(type="done").model_dump_json()
                )

                history.add_user_message(session_id, incoming.message)
                history.add_ai_message(session_id, full_answer)

            except Exception as e:
                logger.exception("RAG chain error")
                await websocket.send_text(
                    WsOutgoing(type="error", content=str(e)).model_dump_json()
                )

    except WebSocketDisconnect:
        pass
