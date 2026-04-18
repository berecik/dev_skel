# Agents Rules for `python-fastapi-rag-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`python-fastapi-rag-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.


## Mandatory Test Artifact Location

- **Mandatory:** Any testing projects, services, data, or files must be created only under `_test_projects/` (the dedicated directory for generated testing skeletons and related test artifacts).

---

## Maintenance Scenario ("let do maintenance" / "let do test-fix loop")

Use this shared scenario whenever the user asks for maintenance (for example: `let do maintenance` or `let do test-fix loop`).

- **1) Finish the requested implementation scenario first.**
- **2) Run tests for changed scope first**, then run full relevant test suites.
- **3) Test code safety** (security/safety checks relevant to the stack and changed paths).
- **4) Simplify and clean up code** (remove dead code, reduce complexity, keep style consistent).
- **5) Run all relevant tests again** after cleanup.
- **6) Fix every issue found** (tests, lint, safety, build, runtime).
- **7) Repeat steps 2–6 until no issues remain.**
- **8) Only then update and synchronize documentation/rules** (`README`, `_docs/`, skeleton docs, agent instructions) to match final behaviour.

This is the default maintenance/test-fix loop and should be commonly understood across all agent entrypoints.

---

## 1. Purpose of This Skeleton

- Provides a FastAPI-based backend skeleton with **LangChain RAG**,
  **ChromaDB** vector database, and a layered DDD-style structure.
- Lives at `_skels/python-fastapi-rag-skel/`.
- Generates test projects like `_test_projects/test-fastapi-rag-app`.
- Three app-layer modules:
  - `app/documents/` — DDD entity for document metadata (upload/list/delete)
  - `app/rag/` — RAG engine (embeddings, vectorstore, LLM, chain, ingestion)
  - `app/chat/` — REST chat + search endpoints, WebSocket streaming
- `core/` is shared infrastructure from `python-fastapi-skel`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`, etc.).
2. Keep FastAPI, LangChain, and ChromaDB reasonably up to date.
3. Ensure generated projects work out of the box with local Ollama + HuggingFace embeddings.

---

## 2. Files to Check First

When working on `python-fastapi-rag-skel`, always inspect these files first:

1. Skeleton documentation: this `AGENTS.md` and `CLAUDE.md`
2. Skeleton Makefile: `_skels/python-fastapi-rag-skel/Makefile`
3. Generator scripts: `gen`, `merge`, `test_skel`
4. RAG engine: `app/rag/config.py`, `app/rag/chain.py`, `app/rag/vectorstore.py`
5. Chat: `app/chat/routes.py`, `app/chat/ws.py`
6. Documents: `app/documents/routes.py`, `app/documents/models.py`
7. Test projects for behaviour reference: `_test_projects/test-fastapi-rag-app/`

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Architecture and Style Constraints

1. `app/rag/` is infrastructure (service layer), NOT a DDD entity module.
   It has no SQLModel table or repository of its own.
2. `app/documents/` follows the standard DDD pattern (models → adapters → depts → routes).
3. `app/chat/` owns the REST and WebSocket endpoints.
4. ChromaDB persistence lives in `<service_dir>/chroma_data/` (service-specific,
   not wrapper-shared).
5. Embeddings and LLM are configured via `RAG_*` env vars in `.env`.
6. WebSocket auth uses `?token=<jwt>` query parameter (not headers).
7. Conversation history defaults to in-memory; SQLite is optional.

---

## 4. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, run:

```bash
cd _skels/python-fastapi-rag-skel && make test
```

The `test_skel` script validates:
1. All module imports succeed.
2. Health endpoints respond.
3. Document upload → search → delete flow works (uses embeddings only, no LLM).
4. Docker image builds.

Chat endpoint (POST /chat) and WebSocket require a running Ollama instance
and are NOT tested in `test_skel`. Test manually when Ollama is available.

---

## 5. Do Not

1. Do not remove or drastically alter the generator entry points.
2. Do not hard-code machine-specific paths or environment assumptions.
3. Do not introduce LangChain pre-release APIs unless explicitly requested.
4. Do not make ChromaDB wrapper-shared — it is per-service by design.
