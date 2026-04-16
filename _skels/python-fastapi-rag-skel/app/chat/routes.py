from typing import Any

from fastapi import APIRouter

from app.rag.depts import RagChainDep, VectorStoreDep, RagSettingsDep
from .models import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResult,
    SearchHit,
    SourceReference,
)
from .history import get_history_store, new_session_id

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    chain: RagChainDep,
    settings: RagSettingsDep,
) -> Any:
    session_id = request.session_id or new_session_id()
    history = get_history_store(max_turns=settings.history_max_turns)

    chat_history = history.get_messages(session_id)

    result = chain.invoke({
        "input": request.message,
        "chat_history": chat_history,
    })

    answer = result.get("answer", "")
    context_docs = result.get("context", [])

    sources = []
    for doc in context_docs:
        sources.append(SourceReference(
            filename=doc.metadata.get("filename", doc.metadata.get("source", "")),
            page_content=doc.page_content[:500],
            chunk_index=doc.metadata.get("chunk_index"),
        ))

    history.add_user_message(session_id, request.message)
    history.add_ai_message(session_id, answer)

    return ChatResponse(answer=answer, sources=sources, session_id=session_id)


@router.post("/search", response_model=SearchResult)
def search(
    request: SearchRequest,
    store: VectorStoreDep,
) -> Any:
    results_with_scores = store.similarity_search_with_score(
        request.query, k=request.top_k,
    )

    hits = []
    for doc, score in results_with_scores:
        hits.append(SearchHit(
            content=doc.page_content,
            metadata=doc.metadata,
            score=round(float(score), 4),
        ))

    return SearchResult(results=hits)
