# RAG Observability & Retrieval Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full observability (timing, scores, verbose output) to the RAG pipeline, expose similarity scores in retrieval, add query prefix optimization, and upgrade the default embedding model to `jinaai/jina-embeddings-v2-base-code` for better code retrieval.

**Architecture:** Instrument the existing RAG modules (`retriever.py`, `embedder.py`, `llm.py`, `agent.py`) with timing and metrics. Add a `verbose` parameter that propagates from the CLI's `-v` flag. Expose FAISS similarity scores in `RetrievedChunk`. Switch the default embedding model and increase chunk size to match the new model's 8192-token context.

**Tech Stack:** Python 3, dataclasses, time.monotonic(), existing `_bin/skel_rag/` modules, `langchain_huggingface`, FAISS.

**Spec:** `_docs/RAG-IMPROVEMENT-PLAN.md` — Phases 1 and 2.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `_bin/skel_rag/metrics.py` | Create | `RagMetrics`, `TargetMetrics`, `RetrievalStats` dataclasses |
| `_bin/skel_rag/retriever.py` | Modify | Add `score` field, `similarity_search_with_score`, timing, verbose output |
| `_bin/skel_rag/embedder.py` | Modify | Add timing on model load |
| `_bin/skel_rag/llm.py` | Modify | Add `chat_with_metrics()` wrapper |
| `_bin/skel_rag/config.py` | Modify | Add `verbose` field to `RagConfig`, update default embedding model |
| `_bin/skel_rag/agent.py` | Modify | Wire verbose + metrics through `_retrieve_block_for_target()` |
| `_bin/skel_rag/tests/test_retriever_metrics.py` | Create | Tests for score exposure and instrumentation |

---

### Task 1: Create the metrics dataclasses

**Files:**
- Create: `_bin/skel_rag/metrics.py`

- [ ] **Step 1: Write the metrics module**

```python
"""Structured metrics for RAG pipeline observability.

Accumulates timing and quality data throughout a generation run.
Cheap to collect (conditional on verbose level), zero overhead at
verbose=0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RetrievalStats:
    """Metrics from one retriever.retrieve() call."""

    query_length: int = 0
    candidates_fetched: int = 0
    results_kept: int = 0
    total_chars: int = 0
    elapsed_s: float = 0.0
    scores: List[float] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def min_score(self) -> float:
        return min(self.scores) if self.scores else 0.0


@dataclass
class LlmCallMetrics:
    """Metrics from one chat() call."""

    elapsed_s: float = 0.0
    input_chars: int = 0
    output_chars: int = 0

    @property
    def input_tokens_est(self) -> int:
        return self.input_chars // 4

    @property
    def output_tokens_est(self) -> int:
        return self.output_chars // 4

    @property
    def throughput_tok_s(self) -> float:
        if self.elapsed_s <= 0:
            return 0.0
        return self.output_tokens_est / self.elapsed_s


@dataclass
class TargetMetrics:
    """Metrics for one target file generation."""

    target_path: str = ""
    retrieval: RetrievalStats = field(default_factory=RetrievalStats)
    llm: LlmCallMetrics = field(default_factory=LlmCallMetrics)


@dataclass
class RagMetrics:
    """Accumulated metrics for one generation run."""

    embedding_load_time_s: float = 0.0
    index_load_time_s: float = 0.0
    corpus_files: int = 0
    corpus_chunks: int = 0
    targets: List[TargetMetrics] = field(default_factory=list)

    @property
    def total_retrieval_time_s(self) -> float:
        return sum(t.retrieval.elapsed_s for t in self.targets)

    @property
    def total_llm_time_s(self) -> float:
        return sum(t.llm.elapsed_s for t in self.targets)
```

- [ ] **Step 2: Verify import**

Run: `cd _bin && python3 -c "from skel_rag.metrics import RagMetrics, RetrievalStats, LlmCallMetrics, TargetMetrics; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add _bin/skel_rag/metrics.py
git commit -m "feat(rag): add metrics dataclasses for observability"
```

---

### Task 2: Add score field to RetrievedChunk and use similarity_search_with_score

**Files:**
- Modify: `_bin/skel_rag/retriever.py`
- Create: `_bin/skel_rag/tests/test_retriever_metrics.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for retriever score exposure and metrics."""

from __future__ import annotations

from skel_rag.retriever import RetrievedChunk


def test_retrieved_chunk_has_score_field():
    chunk = RetrievedChunk(
        rel_path="app/models.py",
        file="/abs/app/models.py",
        language="python",
        kind="class",
        name="Item",
        start_line=10,
        end_line=30,
        source="class Item: pass",
        score=0.85,
    )
    assert chunk.score == 0.85
    assert chunk.header == "app/models.py:10-30 · class · Item"


def test_retrieved_chunk_score_defaults_to_zero():
    chunk = RetrievedChunk(
        rel_path="x.py", file="x.py", language="python",
        kind="function", name="f", start_line=1, end_line=5,
        source="def f(): pass",
    )
    assert chunk.score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd _bin && python3 -m pytest skel_rag/tests/test_retriever_metrics.py -v`
Expected: FAIL — `RetrievedChunk.__init__() got an unexpected keyword argument 'score'`

- [ ] **Step 3: Add score field to RetrievedChunk**

In `_bin/skel_rag/retriever.py`, modify the `RetrievedChunk` dataclass (line 28-48):

```python
@dataclass
class RetrievedChunk:
    """Result of one retrieval hit, decoupled from LangChain types."""

    rel_path: str
    file: str
    language: str
    kind: str
    name: str
    start_line: int
    end_line: int
    source: str
    score: float = 0.0  # cosine similarity (0.0 - 1.0)

    @property
    def header(self) -> str:
        bits = [f"{self.rel_path}:{self.start_line}-{self.end_line}"]
        if self.kind:
            bits.append(self.kind)
        if self.name:
            bits.append(self.name)
        return " · ".join(bits)
```

- [ ] **Step 4: Switch to similarity_search_with_score in retrieve()**

Replace the `similarity_search` call (line 78) and chunk construction (lines 83-96):

```python
    def retrieve(
        self,
        query: str,
        *,
        language: Optional[str] = None,
        file_glob: Optional[str] = None,
        k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """Return up to ``k`` chunks for *query*, language-aware."""

        target_k = k or self.cfg.top_k
        over_fetch = max(target_k * 2, target_k + self.cfg.min_k)

        try:
            results_with_scores = self.store.similarity_search_with_score(
                query, k=over_fetch
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("similarity_search failed: %s", exc)
            return []

        chunks: List[RetrievedChunk] = []
        for doc, score in results_with_scores:
            meta = doc.metadata or {}
            chunk = RetrievedChunk(
                rel_path=str(meta.get("rel_path", meta.get("file", ""))),
                file=str(meta.get("file", "")),
                language=str(meta.get("language", "")),
                kind=str(meta.get("kind", "")),
                name=str(meta.get("name", "")),
                start_line=int(meta.get("start_line", 1) or 1),
                end_line=int(meta.get("end_line", 1) or 1),
                source=doc.page_content or "",
                score=float(score),
            )
            chunks.append(chunk)

        filtered = self._apply_filters(
            chunks, language=language, file_glob=file_glob, target_k=target_k
        )
        return self._budget(filtered, max_chars=self.cfg.max_context_chars)
```

- [ ] **Step 5: Run tests**

Run: `cd _bin && python3 -m pytest skel_rag/tests/test_retriever_metrics.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add _bin/skel_rag/retriever.py _bin/skel_rag/tests/test_retriever_metrics.py
git commit -m "feat(rag): expose similarity scores in RetrievedChunk

Switch from similarity_search() to similarity_search_with_score() so
each chunk carries its cosine similarity score. Enables score-based
filtering, quality metrics, and verbose output."
```

---

### Task 3: Add verbose timing to retriever

**Files:**
- Modify: `_bin/skel_rag/retriever.py`

- [ ] **Step 1: Add timing + verbose to retrieve()**

Add `import sys, time` at the top. Modify `retrieve()` to accept `verbose` and emit timing:

```python
import sys
import time

# ... (existing imports)

from skel_rag.metrics import RetrievalStats
```

Update the `retrieve` method signature and body:

```python
    def retrieve(
        self,
        query: str,
        *,
        language: Optional[str] = None,
        file_glob: Optional[str] = None,
        k: Optional[int] = None,
        verbose: int = 0,
    ) -> tuple[List[RetrievedChunk], RetrievalStats]:
        """Return up to ``k`` chunks for *query* plus retrieval stats."""

        target_k = k or self.cfg.top_k
        over_fetch = max(target_k * 2, target_k + self.cfg.min_k)

        t0 = time.monotonic()

        try:
            results_with_scores = self.store.similarity_search_with_score(
                query, k=over_fetch
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("similarity_search failed: %s", exc)
            return [], RetrievalStats()

        chunks: List[RetrievedChunk] = []
        for doc, score in results_with_scores:
            meta = doc.metadata or {}
            chunk = RetrievedChunk(
                rel_path=str(meta.get("rel_path", meta.get("file", ""))),
                file=str(meta.get("file", "")),
                language=str(meta.get("language", "")),
                kind=str(meta.get("kind", "")),
                name=str(meta.get("name", "")),
                start_line=int(meta.get("start_line", 1) or 1),
                end_line=int(meta.get("end_line", 1) or 1),
                source=doc.page_content or "",
                score=float(score),
            )
            chunks.append(chunk)

        pre_filter_count = len(chunks)
        filtered = self._apply_filters(
            chunks, language=language, file_glob=file_glob, target_k=target_k
        )
        kept = self._budget(filtered, max_chars=self.cfg.max_context_chars)
        elapsed = time.monotonic() - t0

        total_chars = sum(len(c.source) for c in kept)
        stats = RetrievalStats(
            query_length=len(query),
            candidates_fetched=pre_filter_count,
            results_kept=len(kept),
            total_chars=total_chars,
            elapsed_s=elapsed,
            scores=[c.score for c in kept],
        )

        if verbose >= 1:
            print(
                f"    [rag] retrieved {len(kept)}/{pre_filter_count} "
                f"candidates in {elapsed:.2f}s ({total_chars:,} chars)",
                file=sys.stderr,
            )
        if verbose >= 2:
            score_str = ", ".join(f"{s:.2f}" for s in stats.scores[:8])
            print(f"    [rag] scores: [{score_str}]", file=sys.stderr)
            budget_pct = (total_chars / self.cfg.max_context_chars * 100) if self.cfg.max_context_chars else 0
            print(f"    [rag] context: {total_chars:,}/{self.cfg.max_context_chars:,} chars ({budget_pct:.0f}% of budget)", file=sys.stderr)

        return kept, stats
```

- [ ] **Step 2: Verify syntax**

Run: `cd _bin && python3 -c "import py_compile; py_compile.compile('skel_rag/retriever.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add _bin/skel_rag/retriever.py
git commit -m "feat(rag): add timing + verbose output to retriever

At -v: prints candidate count, kept count, elapsed time, char total.
At -vv: prints individual scores and budget utilization percentage.
Returns RetrievalStats alongside chunks for metrics collection."
```

---

### Task 4: Add timing to embedder and LLM

**Files:**
- Modify: `_bin/skel_rag/embedder.py`
- Modify: `_bin/skel_rag/llm.py`

- [ ] **Step 1: Add timing to embedder**

In `_bin/skel_rag/embedder.py`, wrap the model loading with timing:

```python
import sys
import time

# ... existing code ...

def make_embeddings(rag_cfg: RagConfig, verbose: int = 0) -> Any:
    """Return a (cached) ``HuggingFaceEmbeddings`` instance for *rag_cfg*."""

    cache_dir = rag_cfg.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    embeddings = _make_embeddings_cached(rag_cfg.embedding_model, str(cache_dir))
    elapsed = time.monotonic() - t0

    # Only print timing on first load (elapsed > 0.5s means not cached)
    if verbose >= 1 and elapsed > 0.5:
        print(
            f"  [rag] embedding model: {rag_cfg.embedding_model} "
            f"(loaded in {elapsed:.1f}s)",
            file=sys.stderr,
        )

    return embeddings
```

- [ ] **Step 2: Add chat_with_metrics to llm.py**

Append to `_bin/skel_rag/llm.py`:

```python
import sys
import time

from skel_rag.metrics import LlmCallMetrics


def chat_with_metrics(
    config: OllamaConfig, system: str, user: str, *, verbose: int = 0
) -> tuple[str, LlmCallMetrics]:
    """chat() with timing and token estimation."""

    input_chars = len(system) + len(user)

    if verbose >= 2:
        input_tokens_est = input_chars // 4
        print(
            f"    [rag] prompt: system={len(system):,} chars, "
            f"user={len(user):,} chars (~{input_tokens_est:,} tokens)",
            file=sys.stderr,
        )

    t0 = time.monotonic()
    response = chat(config, system=system, user=user)
    elapsed = time.monotonic() - t0

    output_chars = len(response)
    metrics = LlmCallMetrics(
        elapsed_s=elapsed,
        input_chars=input_chars,
        output_chars=output_chars,
    )

    if verbose >= 1:
        print(
            f"    [rag] Ollama: {elapsed:.1f}s, "
            f"response={output_chars:,} chars (~{metrics.output_tokens_est} tokens)",
            file=sys.stderr,
        )
    if verbose >= 2:
        print(
            f"    [rag] throughput: {metrics.throughput_tok_s:.1f} tok/s",
            file=sys.stderr,
        )

    return response, metrics
```

- [ ] **Step 3: Verify both files**

Run: `cd _bin && python3 -c "import py_compile; py_compile.compile('skel_rag/embedder.py', doraise=True); py_compile.compile('skel_rag/llm.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add _bin/skel_rag/embedder.py _bin/skel_rag/llm.py
git commit -m "feat(rag): add timing to embedder load and LLM calls

embedder: prints model name + load time at verbose>=1.
llm: new chat_with_metrics() returns LlmCallMetrics with elapsed,
char counts, token estimates, throughput. Prints at verbose>=1/2."
```

---

### Task 5: Add verbose + query prefix to config

**Files:**
- Modify: `_bin/skel_rag/config.py`

- [ ] **Step 1: Add verbose field and update default model**

In `_bin/skel_rag/config.py`, update the constants and `RagConfig`:

```python
# Line 111 — change default embedding model
DEFAULT_EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-code"

# Line 116 — increase chunk size (8192-token model can handle it)
DEFAULT_CHUNK_MAX_CHARS = 6000
```

Add to the `RagConfig` dataclass (after `fallback_chunk_overlap`):

```python
    verbose: int = 0
```

And in `from_env()`, add:

```python
            verbose=_int("SKEL_AI_VERBOSE", 0),
```

- [ ] **Step 2: Verify**

Run: `cd _bin && python3 -c "from skel_rag.config import RagConfig; c = RagConfig.from_env(); print(f'model={c.embedding_model}, verbose={c.verbose}, chunk_max={c.chunk_max_chars}')"`
Expected: `model=jinaai/jina-embeddings-v2-base-code, verbose=0, chunk_max=6000`

- [ ] **Step 3: Commit**

```bash
git add _bin/skel_rag/config.py
git commit -m "feat(rag): upgrade default embedding model to jina-code-v2

Switch from BAAI/bge-small-en-v1.5 (384D, 512 tok) to
jinaai/jina-embeddings-v2-base-code (768D, 8192 tok).
Increase chunk_max_chars from 2000 to 6000 to exploit the
larger context window. Add verbose field to RagConfig."
```

---

### Task 6: Wire verbose through agent.py

**Files:**
- Modify: `_bin/skel_rag/agent.py`

- [ ] **Step 1: Update _retrieve_block_for_target to pass verbose**

At `_bin/skel_rag/agent.py:516-543`, update the method to use the new retriever API and pass verbose:

```python
    def _retrieve_block_for_target(
        self,
        *,
        retriever: Optional[Retriever],
        target: "AiTarget",
        ctx: "GenerationContext",
        extras: Optional[List[str]] = None,
    ) -> str:
        if retriever is None:
            return _NO_RETRIEVAL_PLACEHOLDER

        query = build_query_for_target(
            target_path=target.path,
            target_description=target.description or "",
            target_prompt=target.prompt or "",
            item_class=ctx.item_class,
            item_name=ctx.item_name,
            items_plural=ctx.items_plural,
            service_label=ctx.service_label,
            auth_type=ctx.auth_type,
            extras=extras,
        )

        # Add model-specific query prefix for better retrieval
        model_name = self.rag_cfg.embedding_model.lower()
        if "bge" in model_name:
            query = f"Represent this code task for retrieval: {query}"
        elif "nomic" in model_name:
            query = f"search_query: {query}"
        # jina-code-v2 needs no prefix

        chunks, stats = retriever.retrieve(
            query,
            language=target.language or None,
            verbose=self.rag_cfg.verbose,
        )

        # Store stats for metrics (if collecting)
        if hasattr(self, '_current_target_metrics') and self._current_target_metrics:
            self._current_target_metrics.retrieval = stats

        return render_retrieved_block(
            chunks, max_chars=self.rag_cfg.max_context_chars
        )
```

- [ ] **Step 2: Verify syntax**

Run: `cd _bin && python3 -c "import py_compile; py_compile.compile('skel_rag/agent.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add _bin/skel_rag/agent.py
git commit -m "feat(rag): wire verbose through agent, add query prefix

_retrieve_block_for_target now passes verbose to retriever and adds
model-specific query prefixes:
- BGE: 'Represent this code task for retrieval: ...'
- Nomic: 'search_query: ...'
- Jina Code v2: no prefix needed"
```

---

### Task 7: Rebuild FAISS indices and verify

**Files:** none (verification only)

- [ ] **Step 1: Clean old indices (built with bge-small 384D)**

Run: `make rag-clean-skels`
Expected: `.skel_rag_index/` directories removed from all skeletons

- [ ] **Step 2: Rebuild with new model**

Run: `SKEL_AI_VERBOSE=1 make rag-index-skels 2>&1 | head -30`
Expected: prints model loading message with `jina-embeddings-v2-base-code`, then indexes each skeleton

- [ ] **Step 3: Verify dry-run still works**

Run: `make test-ai-generators-dry 2>&1 | tail -15`
Expected: all 12 skeletons pass dry-run

- [ ] **Step 4: Run existing RAG tests**

Run: `cd _bin && python3 -m pytest skel_rag/tests/ -v --timeout=120 2>&1 | tail -20`
Expected: all tests pass (some may need `--timeout` due to model loading)

- [ ] **Step 5: Commit index manifests**

```bash
git add _skels/*/.skel_rag_index/manifest.json
git commit -m "chore(rag): rebuild FAISS indices with jina-code-v2

All skeleton indices rebuilt with jinaai/jina-embeddings-v2-base-code
(768D, 8192 context). Old bge-small-en-v1.5 indices removed."
```

---

### Task 8: Verbose integration test

**Files:** none (verification only)

- [ ] **Step 1: Test verbose=1 output**

Run: `SKEL_AI_VERBOSE=1 _bin/skel-gen-ai --dry-run --no-input _test_projects/test-verbose --backend python-fastapi-skel --no-frontend --backend-service-name "Test" --item-name Item --auth-type jwt 2>&1 | grep "\[rag\]"`
Expected: Lines like:
```
  [rag] embedding model: jinaai/jina-embeddings-v2-base-code (loaded in X.Xs)
    [rag] retrieved N/M candidates in 0.XXs (N,NNN chars)
```

- [ ] **Step 2: Test verbose=2 output**

Run: `SKEL_AI_VERBOSE=2 _bin/skel-gen-ai --dry-run --no-input _test_projects/test-verbose --backend python-fastapi-skel --no-frontend --backend-service-name "Test" --item-name Item --auth-type jwt 2>&1 | grep "\[rag\]"`
Expected: All verbose=1 lines plus scores and budget percentage

- [ ] **Step 3: Clean up**

Run: `rm -rf _test_projects/test-verbose`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(rag): complete Phase 1+2 observability and quality upgrade

- Metrics dataclasses (RagMetrics, RetrievalStats, LlmCallMetrics)
- Similarity scores exposed in RetrievedChunk
- Timing at every layer (embedder, retriever, LLM)
- Verbose output: -v (timers), -vv (scores + tokens + budget)
- Default model upgraded to jina-embeddings-v2-base-code (768D, 8K ctx)
- chunk_max_chars increased to 6000 (from 2000)
- Query prefix optimization for BGE/Nomic models
- All FAISS indices rebuilt with new model

Ref: _docs/RAG-IMPROVEMENT-PLAN.md Phases 1-2"
```
