# Rewriting Local Context Retrieval to Use LLM-Based Reranking via Ollama

## Problem

The current RAG pipeline in `_bin/skel_rag/` retrieves context using
**embedding similarity** (FAISS cosine search on `BAAI/bge-small-en-v1.5`
vectors). This is fast but semantically shallow — the 384-dimensional
embedding model ranks by lexical/structural similarity, not by whether a
chunk is actually *useful* for the generation task. Result: the LLM
sometimes receives irrelevant boilerplate while missing the most
informative reference code.

## Goal

Replace (or augment) the embedding-based retrieval with an **LLM
reranking step** where Ollama evaluates each candidate chunk's relevance
to the current generation target, reorders them, and optionally
summarizes or drops low-relevance chunks before they enter the
generation prompt.

## Current Pipeline (What We're Changing)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│ build_query │────►│ FAISS cosine │────►│ post-filter  │────►│ render as   │
│ _for_target │     │ similarity   │     │ (lang, glob, │     │ Markdown    │
│ (prompts.py)│     │ top_k=8*2   │     │  budget)     │     │ block       │
└─────────────┘     └──────────────┘     └──────────────┘     └──────┬──────┘
                                                                      │
                                                          {retrieved_context}
                                                                      │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │ Ollama       │
                                                              │ (generation) │
                                                              └──────────────┘
```

**Key files:**
- `_bin/skel_rag/agent.py:516-543` — `_retrieve_block_for_target()`
- `_bin/skel_rag/retriever.py:58-102` — `Retriever.retrieve()`
- `_bin/skel_rag/prompts.py:33-62` — `render_retrieved_block()`
- `_bin/skel_rag/prompts.py:104-143` — `build_query_for_target()`
- `_bin/skel_rag/config.py:107-181` — `RagConfig`

**Data flow today:**

1. `build_query_for_target()` constructs a natural-language query from
   target metadata (path, description, entity name, auth type, prompt
   snippet).
2. `retriever.retrieve(query)` over-fetches 16 chunks from FAISS,
   filters by language/glob, truncates to budget (12,000 chars).
3. `render_retrieved_block()` formats chunks as Markdown headers + fenced
   code blocks.
4. The rendered block is injected into `{retrieved_context}` in the
   manifest prompt.
5. The full prompt goes to Ollama for generation.

## Proposed Pipeline (LLM Reranking)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│ build_query │────►│ FAISS cosine │────►│ post-filter  │────►│ LLM RERANKER │────►│ render as   │
│ _for_target │     │ similarity   │     │ (lang, glob) │     │ (Ollama)     │     │ Markdown    │
│             │     │ over-fetch   │     │              │     │ score/filter │     │ block       │
└─────────────┘     │ top_k * 3   │     └──────────────┘     └──────────────┘     └──────┬──────┘
                    └──────────────┘                                                       │
                                                                              {retrieved_context}
                                                                                          │
                                                                                          ▼
                                                                                  ┌──────────────┐
                                                                                  │ Ollama       │
                                                                                  │ (generation) │
                                                                                  └──────────────┘
```

The change is a **single insertion point**: between `retriever.retrieve()`
and `render_retrieved_block()`, an LLM call reranks and filters the
candidate chunks.

## Implementation

### New File: `_bin/skel_rag/reranker.py`

```python
"""LLM-based reranking of retrieved chunks via Ollama.

Receives candidate chunks from the FAISS retriever, asks the LLM to
score each chunk's relevance to the generation task, then returns
only the top-scoring chunks in reranked order.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from .config import OllamaConfig, RagConfig
from .llm import chat
from .retriever import RetrievedChunk

log = logging.getLogger(__name__)

RERANK_SYSTEM = """\
You are a code relevance evaluator. Given a coding task description and \
a list of code snippets from a reference codebase, score each snippet's \
relevance to the task on a scale of 0-10.

Output ONLY valid JSON: an array of objects with "index" (0-based) and \
"score" (integer 0-10). Order by score descending. Example:
[{"index": 2, "score": 9}, {"index": 0, "score": 7}, {"index": 1, "score": 3}]

Scoring guide:
- 10: Directly implements the pattern needed (same entity type, same
      operation)
- 7-9: Closely related pattern (different entity but same architecture
       layer)
- 4-6: Indirectly useful (imports, config, utility used by the target)
- 1-3: Marginally related (same file area but different concern)
- 0: Irrelevant to the task
"""

RERANK_USER_TEMPLATE = """\
## Task
Generate: {target_path}
Description: {target_description}
Entity: {item_class} ({items_plural})
Auth: {auth_type}

## Candidate Snippets

{candidates}

## Instructions
Score each snippet (0-10) for relevance to the task above. Return JSON \
array sorted by score descending. Include ALL snippets in your output.
"""


@dataclass
class ScoredChunk:
    chunk: RetrievedChunk
    score: int


def rerank_chunks(
    ollama_cfg: OllamaConfig,
    chunks: List[RetrievedChunk],
    *,
    target_path: str,
    target_description: str,
    item_class: str = "",
    items_plural: str = "",
    auth_type: str = "",
    min_score: int = 4,
    max_chunks: int = 6,
) -> List[RetrievedChunk]:
    """Rerank chunks via Ollama LLM and return top-scoring ones.

    Falls back to the original order if the LLM response is unparseable.
    """
    if not chunks:
        return []

    # Format candidates for the prompt
    candidate_lines = []
    for i, chunk in enumerate(chunks):
        header = f"[{i}] {chunk.rel_path}:{chunk.start_line}-{chunk.end_line}"
        header += f" ({chunk.kind} {chunk.name})"
        # Truncate source to ~800 chars to fit more candidates in context
        source = chunk.source[:800]
        if len(chunk.source) > 800:
            source += "\n... (truncated)"
        candidate_lines.append(f"{header}\n```\n{source}\n```")

    candidates_text = "\n\n".join(candidate_lines)

    user_prompt = RERANK_USER_TEMPLATE.format(
        target_path=target_path,
        target_description=target_description,
        item_class=item_class,
        items_plural=items_plural,
        auth_type=auth_type,
        candidates=candidates_text,
    )

    # Use a lower temperature for deterministic ranking
    rerank_cfg = OllamaConfig(
        model=ollama_cfg.model,
        base_url=ollama_cfg.base_url,
        timeout=min(ollama_cfg.timeout, 120),  # cap at 2 min
        temperature=0.0,
    )

    try:
        response = chat(rerank_cfg, system=RERANK_SYSTEM, user=user_prompt)
        scored = _parse_scores(response, chunks)
    except Exception as exc:
        log.warning("LLM reranker failed (%s), falling back to embedding order", exc)
        return chunks[:max_chunks]

    # Filter by min_score and take top max_chunks
    relevant = [sc for sc in scored if sc.score >= min_score]
    if not relevant:
        # If nothing scored above threshold, keep top 3 by score
        relevant = scored[:3]

    return [sc.chunk for sc in relevant[:max_chunks]]


def _parse_scores(
    response: str, chunks: List[RetrievedChunk]
) -> List[ScoredChunk]:
    """Parse the LLM JSON response into ScoredChunk list."""
    # Strip markdown code fence if present
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Find JSON array in response
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in response: {text[:200]}")

    arr = json.loads(text[start : end + 1])

    scored: List[ScoredChunk] = []
    for entry in arr:
        idx = entry.get("index", -1)
        score = entry.get("score", 0)
        if 0 <= idx < len(chunks):
            scored.append(ScoredChunk(chunk=chunks[idx], score=int(score)))

    # Sort by score descending
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
```

### Modification: `_bin/skel_rag/agent.py`

In `_retrieve_block_for_target()` (around line 530):

```python
# BEFORE (current code):
chunks = retriever.retrieve(query, language=target.language)
block = render_retrieved_block(chunks)

# AFTER (with LLM reranking):
chunks = retriever.retrieve(query, language=target.language)

if self._rag_cfg.use_llm_reranker and chunks:
    from .reranker import rerank_chunks
    chunks = rerank_chunks(
        self._ollama_cfg,
        chunks,
        target_path=target.path,
        target_description=target.description or "",
        item_class=ctx.item_class,
        items_plural=ctx.items_plural,
        auth_type=ctx.auth_type,
        min_score=self._rag_cfg.rerank_min_score,
        max_chunks=self._rag_cfg.rerank_max_chunks,
    )

block = render_retrieved_block(chunks)
```

### Modification: `_bin/skel_rag/config.py`

Add to `RagConfig`:

```python
# LLM reranking (optional — adds one Ollama call per target)
use_llm_reranker: bool = field(default_factory=lambda: (
    os.environ.get("SKEL_RAG_USE_LLM_RERANKER", "").lower() in ("1", "true", "yes")
))
rerank_min_score: int = int(os.environ.get("SKEL_RAG_RERANK_MIN_SCORE", "4"))
rerank_max_chunks: int = int(os.environ.get("SKEL_RAG_RERANK_MAX_CHUNKS", "6"))
```

### Modification: Retriever over-fetch

When LLM reranking is enabled, we want **more candidates** for the LLM to
evaluate (it's good at distinguishing relevance even among lower-ranked
embedding results). Increase the over-fetch multiplier:

```python
# retriever.py — when reranker is active, fetch more candidates
over_fetch = top_k * 3  # instead of top_k * 2
```

This is configurable via increasing `top_k` env var, or we add a
`rerank_over_fetch_multiplier` config.

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| `SKEL_RAG_USE_LLM_RERANKER` | `false` | Enable LLM reranking |
| `SKEL_RAG_RERANK_MIN_SCORE` | `4` | Minimum score (0-10) to keep a chunk |
| `SKEL_RAG_RERANK_MAX_CHUNKS` | `6` | Max chunks after reranking |

## Usage

```bash
# Enable LLM reranking for a generation run
SKEL_RAG_USE_LLM_RERANKER=1 _bin/skel-gen-ai myproject

# Combine with other RAG settings
SKEL_RAG_USE_LLM_RERANKER=1 \
SKEL_RAG_TOP_K=12 \
SKEL_RAG_RERANK_MIN_SCORE=5 \
_bin/skel-gen-ai myproject --backend python-fastapi-skel --no-input
```

## Performance Impact

| Phase | Without reranker | With reranker |
|-------|-----------------|---------------|
| FAISS retrieval | ~50ms | ~50ms (same) |
| LLM rerank call | 0 | 3-8s per target (30B model) |
| Total per target | 30-120s | 33-128s (+3-8s) |
| Full 7-target gen | ~5-10 min | ~5.5-11 min |

The reranking adds 3-8 seconds per target file (one short LLM call with
~2000 tokens input, ~200 tokens output). For a 7-target generation this
is 20-55 seconds extra — a ~5-10% overhead on the total generation time.

The quality improvement should reduce the fix-loop iterations (fewer
irrelevant context → better first-pass code), potentially saving more
time than the reranking costs.

## Alternative Strategies

### Strategy A: Score + Filter (recommended for first iteration)

The approach described above. LLM scores each chunk 0-10, drops anything
below threshold, returns top N in score order.

- **Pros:** Simple, deterministic-ish, preserves original chunk text.
- **Cons:** One extra LLM call per target; scores are noisy with small
  models.

### Strategy B: Summarize + Merge

Instead of scoring, ask the LLM to read all candidates and produce a
**synthesized context block** — a condensed summary of the most relevant
patterns, merged from multiple chunks.

```
System: "Read these code snippets. Synthesize the patterns most relevant
to generating {target_path}. Output a compact reference showing the key
types, function signatures, and architectural patterns needed."
```

- **Pros:** Can fit more information into less context; the generation
  LLM sees a cleaner reference.
- **Cons:** Lossy (may drop important details); harder to debug; the
  synthesis itself may hallucinate patterns that don't exist in the
  original code.

### Strategy C: Two-Pass with Different Models

Use a small/fast model for reranking (e.g., `qwen2.5-coder:7b`) and the
large model for generation (`qwen3-coder:30b`). The 7B model is ~4x
faster for the scoring task, and the quality bar for "score relevance" is
lower than "generate correct code."

```bash
SKEL_RAG_RERANK_MODEL=qwen2.5-coder:7b _bin/skel-gen-ai myproject
```

Add to config:
```python
rerank_model: str = os.environ.get("SKEL_RAG_RERANK_MODEL", "")
# If empty, uses the main OLLAMA_MODEL
```

- **Pros:** Minimal latency impact (~1-2s per target with 7B).
- **Cons:** Small model may misjudge relevance for complex domains.

### Strategy D: Hybrid Embedding + Cross-Encoder

Use a cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
locally instead of an LLM call. Cross-encoders are purpose-built for
reranking — they take (query, document) pairs and output a relevance
score.

```python
from sentence_transformers import CrossEncoder
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
scores = model.predict([(query, chunk.source) for chunk in chunks])
```

- **Pros:** Fast (~100ms for 16 chunks), no Ollama call needed,
  deterministic.
- **Cons:** Less semantic understanding than a full LLM; requires
  `sentence-transformers` dependency; may not understand code as well as
  a code-tuned LLM.

## Fallback Behavior

The reranker MUST NOT break generation if it fails:

1. **LLM timeout/error:** Fall back to embedding order (log warning).
2. **Unparseable JSON:** Fall back to embedding order (log warning).
3. **All chunks score below threshold:** Keep top 3 by score regardless.
4. **Ollama unreachable:** Skip reranking entirely (same as `USE_LLM_RERANKER=false`).

This ensures the generation pipeline never fails because of the reranking
step — it degrades gracefully to the current behavior.

## Testing

```bash
# Unit test: mock Ollama, verify reranker parses scores correctly
pytest _bin/skel_rag/tests/test_reranker.py -v

# Integration test: real Ollama, verify reranking improves context quality
SKEL_RAG_USE_LLM_RERANKER=1 make test-gen-ai-fastapi

# A/B comparison: generate same project with and without reranker
SKEL_RAG_USE_LLM_RERANKER=0 _bin/skel-gen-ai _test_projects/no-rerank ...
SKEL_RAG_USE_LLM_RERANKER=1 _bin/skel-gen-ai _test_projects/with-rerank ...
diff -r _test_projects/no-rerank _test_projects/with-rerank
```

## Migration Path

1. **Phase 1:** Add `reranker.py` + config. Default OFF. Test manually.
2. **Phase 2:** Enable by default for manifests that opt in (via a
   manifest-level `use_reranker = True` flag).
3. **Phase 3:** If quality improvement is confirmed, make it default ON
   for all manifests. Keep the env-var escape hatch for CI/fast runs.
