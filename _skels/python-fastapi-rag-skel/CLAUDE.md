# Claude Code Rules — `python-fastapi-rag-skel`

Claude-specific complement to `_skels/python-fastapi-rag-skel/AGENTS.md`.
Read that first; sections below only add Claude Code conventions.

---

## 1. Skeleton Snapshot

- FastAPI backend skeleton with **LangChain RAG**, **ChromaDB** vector
  database, and a layered DDD-style layout for document management.
- Three app-layer modules:
  - `app/documents/` — DDD entity for document metadata (upload/list/delete)
  - `app/rag/` — RAG engine: embeddings, vector store, LLM, chain, ingestion
  - `app/chat/` — REST (POST /chat, POST /search) + WebSocket (/ws/chat)
- `core/` is shared infrastructure from `python-fastapi-skel` (auth, users,
  repository pattern, SQLAlchemy adapters).
- Generators write into `_test_projects/test-fastapi-rag-app`.

---

## 2. RAG Architecture

- **Embeddings**: HuggingFace `all-MiniLM-L6-v2` (default) or OpenAI.
  Configured via `RAG_EMBEDDING_PROVIDER` / `RAG_EMBEDDING_MODEL`.
- **Vector store**: ChromaDB with local persistence at `RAG_CHROMA_PERSIST_DIR`.
  Singleton via `app/rag/vectorstore.py`.
- **LLM**: Ollama (default) or OpenAI. Configured via `RAG_LLM_PROVIDER`.
- **Chain**: LangChain `create_retrieval_chain` + `create_history_aware_retriever`
  for conversation-aware RAG. See `app/rag/chain.py`.
- **Ingestion**: `app/rag/ingestion.py` — load file → split → embed → store in
  ChromaDB. Supports `.txt`, `.md`, `.pdf`.
- **WebSocket**: `app/chat/ws.py` — token-by-token streaming via `chain.astream()`.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `app/`, `core/`, or the
   skeleton's generator scripts.
2. **Plan dependency bumps.** LangChain / ChromaDB / sentence-transformers
   upgrades touch many files — draft a Plan first.
3. **Default validation after edits**:
   ```bash
   cd _skels/python-fastapi-rag-skel && make test
   ```
4. **Do not hand-edit** `_test_projects/test-fastapi-rag-*` — regenerate with
   `make gen-fastapi-rag NAME=_test_projects/<name>` instead.

---

## 4. Verification Checklist

- [ ] `make test-fastapi-rag` is green (test_skel passes).
- [ ] Document upload + search flow works without Ollama (embeddings only).
- [ ] Chat endpoint works with Ollama running.
- [ ] WebSocket streaming works.
- [ ] AGENTS.md / CLAUDE.md agree.
