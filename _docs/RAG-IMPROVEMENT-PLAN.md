# RAG Pipeline Improvement Plan

Comprehensive plan to improve the `_bin/skel_rag/` pipeline in three
areas: **efficiency** (faster generation, better chunk quality),
**embedding model cooperation** (BertModel tuning, retrieval accuracy),
and **full observability** (metrics, timing, verbose output at every
layer).

---

## Current State Summary

| Component | Timing | Quality Metrics | Verbose Output |
|-----------|--------|----------------|----------------|
| Embedding load | none | none | none |
| FAISS build | none | none | none |
| Chunking (tree-sitter) | none | none (fallback rate unknown) | none |
| Retrieval (similarity) | none | none (score distribution unknown) | none |
| LLM call | heartbeat only | none (no token counts) | `-v` heartbeat |
| Prompt assembly | none | none (context utilization unknown) | none |

The `-v` flag exists at the CLI level but only the heartbeat feature
responds. `-vv` and `-vvv` are documented in the help text but have
no implementation in the RAG layer.

---

## Part 1: Efficiency Improvements

### 1.1 Eager Embedding Model Warm-Up

**Problem:** First retrieval blocks 2-10s loading the embedding model.
This delay happens mid-generation with no visibility.

**Fix:** Pre-load embeddings during `RagAgent.__init__()` instead of
lazily on first `get_retriever()` call.

**Where:** `_bin/skel_rag/agent.py:69-78`

```python
# Current (lazy):
self._embeddings: Any = None

# Proposed (eager with timing):
def __init__(self, ollama_cfg, rag_cfg, verbose=0):
    ...
    if verbose >= 1:
        t0 = time.monotonic()
    self._embeddings = _load_embeddings(rag_cfg)
    if verbose >= 1:
        print(f"  [rag] embedding model loaded in {time.monotonic()-t0:.1f}s",
              file=sys.stderr)
```

### 1.2 Incremental FAISS Index Updates

**Problem:** Any file change triggers full index rebuild (re-embed all
chunks). For a 100-file skeleton this means re-embedding ~500 chunks
even if only 1 file changed.

**Fix:** Track per-file chunk embeddings in the manifest. On rebuild,
only re-embed changed files; reuse cached vectors for unchanged files.

**Where:** `_bin/skel_rag/vectorstore.py:94-131`

```python
# Proposed: store per-file embeddings alongside the FAISS index
# manifest.json gains: {"file.py": {"mtime": ..., "chunks": [...]}}
# On rebuild:
#   1. Diff current manifest vs stored manifest
#   2. Remove stale file embeddings from index
#   3. Embed only new/changed file chunks
#   4. Merge into existing FAISS index
```

**Impact:** Index rebuild drops from 30-120s to 2-10s (delta only).

### 1.3 Batch Query Embedding

**Problem:** Each target file triggers a separate query embedding.
For 7 targets, that's 7 serial embedding calls.

**Fix:** Pre-compute all target queries at the start of
`generate_targets()` and batch-embed them in one call.

**Where:** `_bin/skel_rag/agent.py:162-269`

```python
# Build all queries upfront:
queries = [build_query_for_target(target, ctx) for target in targets]
# Batch embed (HuggingFaceEmbeddings supports list input):
query_vectors = embeddings.embed_documents(queries)
# Then use vector directly in similarity_search_by_vector()
```

**Impact:** ~7x fewer embedding inference calls; saves ~1-3s total.

### 1.4 Parallel Chunk Embedding During Index Build

**Problem:** `FAISS.from_documents()` embeds chunks sequentially.

**Fix:** Use `embed_documents()` batch API explicitly with a larger
batch size before building the FAISS index.

**Where:** `_bin/skel_rag/vectorstore.py:117-123`

```python
# Current:
store = FAISS.from_documents(documents, embeddings)

# Proposed:
texts = [doc.page_content for doc in documents]
vectors = embeddings.embed_documents(texts)  # batched
store = FAISS.from_embeddings(
    text_embeddings=list(zip(texts, vectors)),
    embedding=embeddings,
    metadatas=[doc.metadata for doc in documents],
)
```

### 1.5 Tree-Sitter Parser Pre-warming

**Problem:** First parse per language incurs parser load time (~200ms).
With 10+ languages across skeletons, this adds up.

**Fix:** Pre-warm parsers for all languages found in the corpus during
index build (before the per-file loop).

**Where:** `_bin/skel_rag/chunker.py:221` (`_get_parser`)

```python
# After corpus walk, detect languages and pre-warm:
languages = {detect_language(f) for f in corpus.files}
for lang in languages:
    _get_parser(lang)  # populates @lru_cache
```

---

## Part 2: Embedding Model (BertModel) Cooperation & Ollama Integration

### 2.1 Available Embedding Options — Complete Catalog

#### A. HuggingFace / sentence-transformers (in-process, current approach)

| Model | Dims | Size | Context | Code Score | Interface |
|-------|------|------|---------|-----------|-----------|
| **`BAAI/bge-small-en-v1.5`** | 384 | 130MB | 512 tok | Baseline | **Current default** |
| `BAAI/bge-base-en-v1.5` | 768 | 440MB | 512 tok | +8% | Drop-in replacement |
| `BAAI/bge-large-en-v1.5` | 1024 | 1.3GB | 512 tok | +12% | Drop-in, GPU preferred |
| `BAAI/bge-m3` | 1024 | 2.2GB | **8192** tok | +15% | Requires `FlagEmbedding` lib |
| **`jinaai/jina-embeddings-v2-base-code`** | 768 | 550MB | **8192** tok | **+25% on code** | Drop-in, code-native |
| `nomic-ai/nomic-embed-text-v1.5` | 768 | 560MB | **8192** tok | +12% | Drop-in, needs `search_query:` prefix |
| `nomic-ai/modernbert-embed-base` | 768 | 400MB | **8192** tok | +18% (code in training) | Drop-in, needs prefix |
| `lightonai/modernbert-embed-large` | 1024 | 1.2GB | **8192** tok | +22% | Drop-in, GPU preferred |

#### B. Ollama-served embedding models (via `/api/embed` + `OllamaEmbeddings`)

| Model (Ollama ID) | Dims | Size | Context | Code Score | Notes |
|-------------------|------|------|---------|-----------|-------|
| `nomic-embed-text` (v1.5) | 768 (Matryoshka) | 274MB | **8192** tok | Good | Best quality/size ratio |
| `nomic-embed-text-v2-moe` | 768 (Matryoshka) | 300MB | **8192** tok | Good | MoE, 100+ languages |
| `mxbai-embed-large` | 1024 | 670MB | 512 tok | Good+ | Beat OpenAI text-embedding-3-large (Mar 2024) |
| `snowflake-arctic-embed2` | 1024 (Matryoshka) | 1.1GB | **8192** tok | Good+ | Multilingual |
| `bge-m3` | 1024 | 1.2GB | **8192** tok | Good+ | Dense + sparse + ColBERT |
| **`qwen3-embedding:0.6b`** | 1024 (MRL) | 1.2GB | **8192** tok | **Very good** | Code-aware, instruction-driven |
| **`qwen3-embedding:4b`** | 2560 (MRL) | 8GB | **8192** tok | **Excellent** | Strong code retrieval |
| **`qwen3-embedding:8b`** | 4096 (MRL) | 16GB | **8192** tok | **#1 MTEB (70.58)** | Best available, needs GPU |
| `all-minilm` | 384 | 50MB | 256 tok | Poor | Prototyping only |

*MRL = Matryoshka Representation Learning (dimensions truncatable without retraining)*

#### C. Cross-encoder reranking models (for second-pass scoring)

| Model | Size | Latency (16 chunks) | Code Support |
|-------|------|-------------------|-------------|
| `jinaai/jina-reranker-v2-base-multilingual` | 1.1GB | ~100ms | **Explicit code + function-calling** |
| `BAAI/bge-reranker-v2-m3` | 1.1GB | ~120ms | Good |
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | 34MB | ~70ms | General only |

### 2.2 Maximum Quality Combination

The **best possible combination** for code RAG with Ollama + FAISS:

```
┌──────────────────────────────────────────────────────────────────────┐
│  MAXIMUM QUALITY PIPELINE                                            │
│                                                                      │
│  Embedding:  qwen3-embedding:0.6b (via Ollama)                      │
│              or jinaai/jina-embeddings-v2-base-code (via HuggingFace)│
│  Index:      FAISS IndexFlatIP (normalized cosine)                   │
│  Reranker:   jinaai/jina-reranker-v2-base-multilingual              │
│  Generator:  qwen3-coder:30b (via Ollama)                           │
│                                                                      │
│  Flow: embed query → FAISS top-16 → reranker top-6 → generate      │
└──────────────────────────────────────────────────────────────────────┘
```

**Why this combination:**

| Component | Choice | Reasoning |
|-----------|--------|-----------|
| **Embedder** | `qwen3-embedding:0.6b` (Ollama) or `jina-code-v2` (HF) | Code-native training; 8192 context fits whole functions; 1024D/768D captures more semantic nuance than 384D |
| **FAISS index** | `IndexFlatIP` with normalized vectors | Exact cosine search; corpus is small (<1000 chunks) so brute-force is fast |
| **Reranker** | `jina-reranker-v2` cross-encoder | Purpose-built for code; 100ms for 16 chunks; no Ollama call needed |
| **Generator** | `qwen3-coder:30b` | Current default, strong code generation |

**Performance comparison (estimated for FastAPI skeleton, 87 files, ~420 chunks):**

| Config | Index Build | Per-Query Retrieval | Quality (relative) |
|--------|------------|--------------------|--------------------|
| Current (`bge-small`, no reranker) | 15s | 50ms | Baseline |
| `jina-code-v2` + reranker | 25s | 150ms (50ms embed + 100ms rerank) | **+30-40%** |
| `qwen3-embedding:0.6b` + reranker | 40s | 200ms (100ms embed via Ollama + 100ms rerank) | **+35-45%** |
| `qwen3-embedding:8b` + reranker | 120s | 300ms | **+50%** (overkill for this corpus size) |

### 2.3 Recommended Upgrade Path

**Tier 1 — Immediate (zero-risk, high impact):**

```python
# _bin/skel_rag/config.py — change one constant
DEFAULT_EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-code"
# was: "BAAI/bge-small-en-v1.5"
```

Plus add the BGE query prefix for backward compat:

```python
# _bin/skel_rag/retriever.py — before similarity_search()
model_name = self._cfg.embedding_model.lower()
if "bge" in model_name:
    query = f"Represent this code task for retrieval: {query}"
elif "nomic" in model_name:
    query = f"search_query: {query}"
# jina-code-v2 needs NO prefix
```

After this change, run `make rag-clean-skels && make rag-index-skels`
to rebuild indices with the new model.

**Tier 2 — Add cross-encoder reranking (medium effort):**

```python
# _bin/skel_rag/reranker.py (new file)
from sentence_transformers import CrossEncoder

_reranker: CrossEncoder = None

def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("jinaai/jina-reranker-v2-base-multilingual")
    return _reranker

def rerank(query: str, chunks: list[RetrievedChunk], top_k: int = 6) -> list[RetrievedChunk]:
    pairs = [(query, chunk.source) for chunk in chunks]
    scores = get_reranker().predict(pairs)
    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_k]]
```

**Tier 3 — Switch to Ollama embeddings (for GPU-accelerated embedding):**

```python
# _bin/skel_rag/embedder.py — add Ollama backend
from langchain_ollama import OllamaEmbeddings

def make_embeddings(cfg: RagConfig):
    if cfg.embedding_backend == "ollama":
        return OllamaEmbeddings(
            model=cfg.embedding_model,  # e.g. "qwen3-embedding:0.6b"
            base_url=cfg.ollama_base_url,
        )
    else:
        # Current HuggingFace path
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=cfg.embedding_model,
            cache_folder=str(cfg.cache_dir),
            encode_kwargs={"normalize_embeddings": True},
        )
```

New config:
```bash
SKEL_RAG_EMBEDDING_BACKEND=ollama          # or "huggingface" (default)
SKEL_RAG_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

### 2.4 Ollama Embedding vs HuggingFace: When to Use Which

| Factor | HuggingFace (in-process) | Ollama (API) |
|--------|--------------------------|--------------|
| **Latency** | ~2-5ms/query (GPU), ~10-30ms/query (CPU) | ~15-50ms/query (HTTP overhead) |
| **Throughput** | Higher (no serialization) | Lower (~2x slower) |
| **GPU contention** | Shares with Python process | Managed separately; may contend with generator |
| **Dependencies** | PyTorch + transformers (~2GB pip) | Just `langchain-ollama` (~lightweight) |
| **Model management** | Manual download + cache | `ollama pull` — centralized |
| **Best for** | Small corpus, CPU-only, fast indexing | GPU-heavy setups where Ollama manages all models |

**Recommendation for dev_skel:** Stay with **HuggingFace in-process**
for embeddings. The corpus is small (~500 chunks), indexing is
infrequent, and you want the generator model (`qwen3-coder:30b`) to
have full GPU access. Ollama embeddings make sense only if you already
have `qwen3-embedding` loaded for other purposes.

### 2.5 Context Window Impact

The current `bge-small` has **512 tokens** max. Your `chunk_max_chars`
is 2000 (~500 tokens). Chunks at the limit get silently truncated.

With an 8192-token model (Jina Code v2, Nomic, Qwen3-Embedding):

| Chunk Strategy | bge-small (512 tok) | jina-code-v2 (8192 tok) |
|----------------|--------------------|-----------------------|
| `chunk_max_chars=2000` | Truncates large functions | Fits perfectly |
| `chunk_max_chars=6000` | Severe truncation | Fits (whole classes) |
| `chunk_max_chars=16000` | Unusable | Fits (whole modules) |
| No chunking (whole files) | Unusable | Works for files <32K chars |

**Recommended change with Jina Code v2:**
```python
DEFAULT_CHUNK_MAX_CHARS = 6000   # was 2000
# Now entire classes/large functions can be one chunk
```

### 2.6 Embedding Quality Validation

Add a self-test that verifies the embedding model can distinguish
relevant from irrelevant code:

```python
# _bin/skel_rag/tests/test_embedding_quality.py

def test_code_relevance_separation():
    """Verify embeddings separate related from unrelated code."""
    embeddings = load_embeddings(rag_cfg)

    query = "FastAPI route handler for creating items with JWT auth"
    relevant = "async def create_item(item: ItemCreate, user: User = Depends(get_current_user)):"
    irrelevant = "body { margin: 0; font-family: sans-serif; }"

    q_vec = embeddings.embed_query(query)
    r_vec = embeddings.embed_documents([relevant])[0]
    i_vec = embeddings.embed_documents([irrelevant])[0]

    sim_relevant = cosine_similarity(q_vec, r_vec)
    sim_irrelevant = cosine_similarity(q_vec, i_vec)

    assert sim_relevant > sim_irrelevant + 0.2, (
        f"Embedding model can't distinguish code relevance: "
        f"relevant={sim_relevant:.3f}, irrelevant={sim_irrelevant:.3f}"
    )
```

### 2.7 Similarity Score Exposure

**Problem:** FAISS returns scores but the retriever discards them.
Without scores, we can't measure retrieval quality or set thresholds.

**Fix:** Use `similarity_search_with_score()` and propagate scores:

**Where:** `_bin/skel_rag/retriever.py:78`

```python
# Current:
results = self.store.similarity_search(query, k=over_fetch)

# Proposed:
results_with_scores = self.store.similarity_search_with_score(query, k=over_fetch)
# Returns List[Tuple[Document, float]]
```

Add `score` field to `RetrievedChunk`:

```python
@dataclass
class RetrievedChunk:
    ...
    score: float = 0.0  # cosine similarity (0.0 - 1.0)
```

This enables:
- Score-based filtering (drop chunks below threshold)
- Quality metrics (track avg score per generation)
- Verbose output showing why a chunk was selected

### 2.8 FAISS Index Type Selection

Current: `IndexFlatIP` with `normalize_embeddings=True`.

This is correct for all models that produce normalized vectors (BGE,
Jina, Nomic, Qwen3-Embedding all do). With normalized vectors:

```
cosine_similarity(a, b) = dot_product(a, b)   # when ||a|| = ||b|| = 1
```

So `IndexFlatIP` (inner product) gives cosine similarity directly.
No change needed when switching embedding models — as long as
`normalize_embeddings=True` is set (or the model normalizes
internally like Qwen3-Embedding does).

For larger corpora (>10K chunks), consider `IndexIVFFlat` with
`nlist=sqrt(n_chunks)` for approximate search. For dev_skel's ~500
chunk corpus, brute-force `IndexFlatIP` is optimal (exact results,
<50ms).

### 2.9 Qwen3-Coder Cannot Embed

**Important:** `qwen3-coder:30b` (the generation model) is a
decoder-only model and CANNOT produce embeddings. Ollama's
`/api/embed` endpoint rejects it.

The Qwen3 family has separate embedding models:
- `qwen3-embedding:0.6b` — fast, code-aware, 1024D
- `qwen3-embedding:4b` — high quality, 2560D
- `qwen3-embedding:8b` — #1 MTEB, 4096D

These are purpose-built encoder models that share the Qwen3 tokenizer
but have a completely different architecture. They coexist with the
generation model in Ollama's model cache.

---

## Part 3: Full Observability

### 3.1 Structured Metrics Dataclass

Add a metrics collector that accumulates timing and quality data
throughout a generation run:

```python
# _bin/skel_rag/metrics.py

@dataclass
class RagMetrics:
    """Accumulated metrics for one generation run."""

    # Timing (seconds)
    embedding_load_time: float = 0.0
    index_build_time: float = 0.0
    index_load_time: float = 0.0
    total_retrieval_time: float = 0.0
    total_llm_time: float = 0.0
    total_prompt_assembly_time: float = 0.0

    # Per-target metrics
    targets: List[TargetMetrics] = field(default_factory=list)

    # Corpus stats
    corpus_files: int = 0
    corpus_chunks: int = 0
    tree_sitter_success: int = 0
    tree_sitter_fallback: int = 0
    index_size_bytes: int = 0

    def summary(self) -> str:
        """Human-readable summary for verbose output."""
        ...

    def to_json(self) -> dict:
        """Machine-readable export for observability pipelines."""
        ...


@dataclass
class TargetMetrics:
    """Metrics for one target file generation."""

    target_path: str
    retrieval_time_s: float = 0.0
    retrieval_candidates: int = 0      # pre-filter
    retrieval_results: int = 0         # post-filter
    retrieval_chars: int = 0           # total context chars used
    retrieval_avg_score: float = 0.0   # avg similarity score
    retrieval_min_score: float = 0.0   # lowest score kept
    llm_time_s: float = 0.0
    llm_input_chars: int = 0           # prompt size
    llm_output_chars: int = 0          # response size
    llm_input_tokens_est: int = 0      # estimated (~4 chars/token)
    llm_output_tokens_est: int = 0
```

### 3.2 Verbose Output Levels

Implement the three levels documented in `skel-gen-ai --help`:

| Level | Env Var | What It Shows |
|-------|---------|---------------|
| `-v` (1) | `SKEL_AI_VERBOSE=1` | Phase timers, Ollama heartbeat, index load/build time |
| `-vv` (2) | `SKEL_AI_VERBOSE=2` | + prompt/response sizes, retrieval scores, chunk selection reasoning, token estimates |
| `-vvv` (3) | `SKEL_AI_VERBOSE=3` | + full prompt dumps to `.ai/<run>/debug/`, per-chunk scores, FAISS query vectors |

#### Level 1 output example:

```
  [rag] embedding model: BAAI/bge-small-en-v1.5 (loaded in 2.1s)
  [rag] corpus: python-fastapi-skel (87 files, 423 chunks)
  [rag] index: loaded from cache in 0.3s (1.2MB)
  [1/7] app/orders_api/__init__.py — module marker
    [rag] retrieved 6 chunks in 0.05s (4,231 chars)
    [rag] Ollama qwen3-coder:30b ... 45s elapsed... done (52s)
  [2/7] app/orders_api/models.py — pydantic + abstract layer
    [rag] retrieved 8 chunks in 0.04s (11,892 chars)
    [rag] Ollama qwen3-coder:30b ... 120s elapsed... done (134s)
```

#### Level 2 output example (adds detail):

```
  [rag] embedding model: BAAI/bge-small-en-v1.5 (loaded in 2.1s, 384 dims)
  [rag] corpus: python-fastapi-skel (87 files, 423 chunks, 12 languages)
  [rag]   tree-sitter: 401/423 chunks (95.0%), fallback: 22/423 (5.0%)
  [rag] index: loaded from cache in 0.3s (1.2MB, 423 vectors)
  [2/7] app/orders_api/models.py — pydantic + abstract layer
    [rag] query: "app/orders_api/models.py\nentity Order (order, orders)..."
    [rag] retrieved 8/16 candidates (scores: 0.82, 0.79, 0.71, 0.68, 0.65, 0.61, 0.58, 0.54)
    [rag] context: 11,892 chars (~2,973 tokens) — 99.1% of budget
    [rag] prompt: system=1,240 chars, user=14,103 chars (~3,836 tokens total)
    [rag] Ollama: 134s, response=4,190 chars (~1,048 tokens)
    [rag] throughput: 7.8 tok/s (output), context utilization: 99%
```

#### Level 3 output (adds file dumps):

```
  [rag] debug dump: .ai/run-20260427-120500/debug/
    target-2-models.py-query.txt        (query text)
    target-2-models.py-retrieved.md     (full retrieved block)
    target-2-models.py-prompt.txt       (full system+user prompt)
    target-2-models.py-response.txt     (raw LLM response)
    target-2-models.py-metrics.json     (per-target metrics)
```

### 3.3 Implementation: Instrumented Retriever

```python
# _bin/skel_rag/retriever.py — instrumented version

def retrieve(
    self,
    query: str,
    *,
    language: Optional[str] = None,
    glob_filter: Optional[str] = None,
    verbose: int = 0,
) -> Tuple[List[RetrievedChunk], RetrievalStats]:
    """Retrieve + return stats for observability."""

    t0 = time.monotonic()

    # Over-fetch from FAISS with scores
    results_with_scores = self.store.similarity_search_with_score(
        query, k=self._over_fetch
    )

    # Convert to RetrievedChunk with scores
    candidates = []
    for doc, score in results_with_scores:
        chunk = RetrievedChunk(
            rel_path=doc.metadata["rel_path"],
            file=doc.metadata.get("file", ""),
            language=doc.metadata.get("language", ""),
            kind=doc.metadata.get("kind", ""),
            name=doc.metadata.get("name", ""),
            start_line=doc.metadata.get("start_line", 0),
            end_line=doc.metadata.get("end_line", 0),
            source=doc.page_content,
            score=float(score),
        )
        candidates.append(chunk)

    pre_filter_count = len(candidates)

    # Apply filters
    if language:
        candidates = [c for c in candidates if c.language == language]
        # min_k fallback...

    # Budget truncation
    kept = []
    total_chars = 0
    for chunk in candidates[:self._top_k]:
        if total_chars + len(chunk.source) > self._max_context_chars:
            break
        kept.append(chunk)
        total_chars += len(chunk.source)

    elapsed = time.monotonic() - t0

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

    return kept, stats
```

### 3.4 Implementation: Instrumented LLM Call

```python
# _bin/skel_rag/llm.py — add timing + token estimation

def chat_with_metrics(
    config: OllamaConfig,
    system: str,
    user: str,
    verbose: int = 0,
) -> Tuple[str, LlmCallMetrics]:
    """chat() with full metrics collection."""

    input_chars = len(system) + len(user)
    input_tokens_est = input_chars // 4  # rough estimate

    if verbose >= 2:
        print(
            f"    [rag] prompt: system={len(system):,} chars, "
            f"user={len(user):,} chars (~{input_tokens_est:,} tokens)",
            file=sys.stderr,
        )

    t0 = time.monotonic()
    response = chat(config, system=system, user=user)
    elapsed = time.monotonic() - t0

    output_chars = len(response)
    output_tokens_est = output_chars // 4
    throughput = output_tokens_est / elapsed if elapsed > 0 else 0

    metrics = LlmCallMetrics(
        elapsed_s=elapsed,
        input_chars=input_chars,
        output_chars=output_chars,
        input_tokens_est=input_tokens_est,
        output_tokens_est=output_tokens_est,
        throughput_tok_s=throughput,
    )

    if verbose >= 1:
        print(
            f"    [rag] Ollama: {elapsed:.1f}s, "
            f"response={output_chars:,} chars (~{output_tokens_est} tokens)",
            file=sys.stderr,
        )
    if verbose >= 2:
        print(
            f"    [rag] throughput: {throughput:.1f} tok/s",
            file=sys.stderr,
        )

    return response, metrics
```

### 3.5 Implementation: Instrumented Chunker

```python
# _bin/skel_rag/chunker.py — add stats tracking

@dataclass
class ChunkingStats:
    total_files: int = 0
    total_chunks: int = 0
    tree_sitter_files: int = 0
    tree_sitter_chunks: int = 0
    ast_fallback_files: int = 0
    ast_fallback_chunks: int = 0
    text_fallback_files: int = 0
    text_fallback_chunks: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    avg_chunk_chars: float = 0.0
    max_chunk_chars: int = 0
    elapsed_s: float = 0.0
```

### 3.6 Metrics Export (JSON + stderr)

After a generation run completes, dump the full metrics:

```python
# At end of agent.generate_targets():
if verbose >= 2:
    print(f"\n  [rag] === Generation Metrics ===", file=sys.stderr)
    print(f"  [rag] Corpus: {metrics.corpus_files} files, "
          f"{metrics.corpus_chunks} chunks", file=sys.stderr)
    print(f"  [rag] Index: {metrics.index_size_bytes/1024:.0f}KB, "
          f"loaded in {metrics.index_load_time:.1f}s", file=sys.stderr)
    print(f"  [rag] Retrievals: {len(metrics.targets)}x, "
          f"avg {sum(t.retrieval_time_s for t in metrics.targets)/len(metrics.targets)*1000:.0f}ms",
          file=sys.stderr)
    print(f"  [rag] LLM total: {metrics.total_llm_time:.1f}s, "
          f"avg {metrics.total_llm_time/len(metrics.targets):.1f}s/target",
          file=sys.stderr)

if verbose >= 3:
    # Dump full metrics to JSON file
    debug_dir = service_dir / ".ai" / f"run-{timestamp}" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "metrics.json").write_text(
        json.dumps(metrics.to_json(), indent=2)
    )
```

### 3.7 OpenTelemetry Integration (Optional)

For production-grade observability, add OTel spans:

```python
# _bin/skel_rag/otel.py (optional, only when otel SDK installed)

from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode
    tracer = trace.get_tracer("skel_rag")
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False

@contextmanager
def span(name: str, attributes: dict = None):
    if not HAS_OTEL:
        yield None
        return
    with tracer.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                s.set_attribute(f"skel_rag.{k}", v)
        yield s
```

Usage:
```python
with span("retrieve", {"target": target_path, "top_k": top_k}):
    chunks = retriever.retrieve(query)
```

This integrates with the existing Grafana Tempo stack that
`common-wrapper.sh` scaffolds via the `observability` docker-compose
profile.

---

## Part 4: Verbose RAG — Maximum Transparency Mode

### 4.1 Design Principle

When `SKEL_AI_VERBOSE=3` (or `-vvv`), the RAG pipeline should be
**completely transparent** — every decision, every score, every chunk
selection/rejection should be visible. This is essential for prompt
engineering and debugging generation quality.

### 4.2 Per-Target Debug Dump

For each target file generated, dump:

```
.ai/run-<timestamp>/debug/
├── corpus-stats.json              # chunking stats, language breakdown
├── target-1-init/
│   ├── query.txt                  # the retrieval query
│   ├── candidates.json            # all FAISS results with scores
│   ├── selected.json              # chunks kept after filtering
│   ├── rejected.json              # chunks dropped (with reason)
│   ├── retrieved-block.md         # rendered Markdown block
│   ├── system-prompt.txt          # full system message
│   ├── user-prompt.txt            # full user message
│   ├── response.txt               # raw LLM response
│   └── metrics.json               # timing, tokens, scores
├── target-2-models/
│   └── ...
└── run-summary.json               # aggregate metrics
```

### 4.3 Rejection Reasons

When verbose >= 2, log WHY each chunk was dropped:

```
    [rag] chunk rejected: handlers/auth.rs:10-45 (score=0.31, below min=0.40)
    [rag] chunk rejected: config.py:1-20 (budget exhausted: 12,000/12,000 chars)
    [rag] chunk rejected: test_items.py:5-30 (language filter: rust != python)
```

### 4.4 Context Utilization Report

After each retrieval, report how effectively the context budget is used:

```
    [rag] context budget: 11,892/12,000 chars (99.1% utilized)
    [rag] chunk sizes: [2103, 1876, 1654, 1432, 1298, 1187, 1142, 1200]
    [rag] largest gap: chunk 4→5 (score drop: 0.68→0.61)
```

---

## Part 5: Implementation Checklist

### Phase 1: Observability Foundation (do first)

- [ ] Create `_bin/skel_rag/metrics.py` with `RagMetrics` and
      `TargetMetrics` dataclasses
- [ ] Add `verbose: int` parameter to `RagAgent.__init__()`, propagate
      from CLI's `-v` count
- [ ] Instrument `_get_embeddings()` with timing (verbose >= 1)
- [ ] Instrument `vectorstore.load_or_build()` with timing + size
      (verbose >= 1)
- [ ] Instrument `retriever.retrieve()` with timing + candidate counts
      (verbose >= 1)
- [ ] Add `similarity_search_with_score()` — expose scores in
      `RetrievedChunk`
- [ ] Instrument `llm.chat()` with timing + char counts (verbose >= 1)
- [ ] Add token estimation (chars / 4) at verbose >= 2
- [ ] Add debug dump directory at verbose >= 3
- [ ] Wire everything through: `skel-gen-ai -v` → `SKEL_AI_VERBOSE` →
      `RagAgent(verbose=level)` → every instrumented call
- [ ] Test: `_bin/skel-gen-ai -vvv --dry-run` shows full verbose without
      calling Ollama

### Phase 2: Retrieval Quality (requires Phase 1 metrics to measure)

- [ ] Add `score` field to `RetrievedChunk`
- [ ] Add BGE query prefix (`"Represent this code task..."`)
- [ ] Add score-based filtering (configurable threshold via
      `SKEL_RAG_MIN_SCORE`)
- [ ] Add chunking stats to `ChunkingStats` — track tree-sitter vs
      fallback per language
- [ ] Add embedding quality self-test
      (`test_embedding_quality.py`)
- [ ] Document model selection guidance (when to use base vs small vs
      code-tuned)

### Phase 3: Efficiency (requires Phase 2 for measurement)

- [ ] Eager embedding warm-up in `RagAgent.__init__()`
- [ ] Incremental FAISS index updates (delta rebuild)
- [ ] Batch query embedding for multi-target generation
- [ ] Parser pre-warming for detected languages
- [ ] Benchmark: measure before/after on the pizzeria generation test

### Phase 4: LLM Reranking (optional, builds on Phase 1-3)

- [ ] Implement `reranker.py` (see `_docs/RAG-LLM-RERANKING.md`)
- [ ] Add `SKEL_RAG_USE_LLM_RERANKER` config
- [ ] A/B test: compare generation quality with/without reranker
- [ ] Tune reranking prompt based on metrics from Phase 1

### Phase 5: Dedicated Fix-Loop Model (`OLLAMA_FIX_MODEL`)

- [ ] Add `OLLAMA_FIX_MODEL` env var to `config.py` (default:
      `qwen2.5-coder:32b`)
- [ ] Create `OllamaConfig.for_fix()` that uses `OLLAMA_FIX_MODEL`
- [ ] Update `agent.py:fix_target()` to use the fix config
- [ ] Enrich fix-loop RAG context (retrieve from skeleton corpus too,
      not just wrapper siblings)
- [ ] Add `/no_think` sentinel to fix prompts when model is qwen3
- [ ] Benchmark: compare fix success rates across models

---

## Part 6: Dedicated Fix-Loop Model and RAG-Enhanced Fixing

### 6.1 The Problem

The test-fix loop currently uses the **same model** for both generation
and repair. This is suboptimal because:

1. **Generation** benefits from creativity and comprehensive output —
   a larger, slower model with thinking (e.g., `qwen3-coder:30b`) is
   better.
2. **Fixing** benefits from precision, speed, and minimal changes — a
   model that doesn't over-explain and follows "patch only" instructions
   (e.g., `qwen2.5-coder:32b`) is better.
3. The fix loop iterates 5-10 times — speed compounds. A model that's
   3x faster but equally accurate per-fix wins on wall-clock time.

### 6.2 Model Comparison for Test-Fix

| Model | Fix Accuracy (Aider) | Speed (Apple Silicon) | Thinking | Verdict |
|-------|---------------------|----------------------|----------|---------|
| **`qwen2.5-coder:32b`** | **73.7%** | ~10 tok/s | None | **Best fix model** — highest repair score, no wasted tokens |
| `qwen3-coder:30b` | ~69% (SWE-bench) | ~40 tok/s (MoE) | Yes (disable with `/no_think`) | Best speed; slightly less accurate per-fix but more iterations fit |
| `gemma4:31b` | untested | ~15 tok/s | None | Stability issues in Ollama; not recommended |
| `deepseek-r1:70b` | High (complex bugs) | ~6 tok/s | Always | **Escalation only** — too slow for the loop; reserve for stuck bugs |

**Recommendation:**

- `OLLAMA_MODEL=qwen3.6:27b` — generation (LiveCodeBench 83.9,
  SWE-bench 77.2%, dense 27B, 262K context)
- `OLLAMA_FIX_MODEL=qwen2.5-coder:32b` — fix loops (73.7% Aider
  repair, best instruction following for minimal patches)
- Use `qwen3-coder:30b` (with `/no_think`) when `fix_timeout_m` is
  short and you need fast iteration (MoE: 40 tok/s)
- Escalate to `deepseek-r1:70b` after 3+ failed attempts (future)

### 6.3 Why Thinking Mode Hurts Fixing

Thinking (chain-of-thought) adds 30-50% token overhead:

```
<think>
Let me analyze the error... The traceback shows... I think the issue
is... Let me consider... Actually wait, maybe it's... No, the first
interpretation was correct...
</think>

Here's the fixed code:
```

For a fix loop this means:
- 30-50% more generation time per iteration
- 5-10 iterations × 30% overhead = **1.5-5 minutes wasted** per run
- The "exploration" often leads to over-patching (changing code that
  doesn't need changing)

When `OLLAMA_FIX_MODEL` points to a `qwen3` model, the fix prompt
should include `/no_think` to disable the thinking block.

### 6.4 RAG-Enhanced Fix Loop

The current `fix_target()` retrieves from the **wrapper corpus** (sibling
services). This helps when the bug is a cross-service integration issue.
But it misses the **skeleton corpus** — reference implementations of the
same patterns the generated code is trying to follow.

**Proposed enhancement:** Retrieve from BOTH corpora:

```python
# agent.py:fix_target() — enhanced retrieval

# 1. Existing: retrieve from wrapper (sibling API surfaces)
wrapper_block = self._retrieve_block_for_target(
    retriever=wrapper_retriever, target=target, ctx=ctx,
    extras=[f"test error: {test_run.combined_output()[:500]}"],
)

# 2. NEW: retrieve from skeleton corpus (reference patterns)
skel_retriever = self.get_retriever(
    corpus_for_skeleton(ctx.skeleton_path)
)
skeleton_block = self._retrieve_block_for_target(
    retriever=skel_retriever, target=target, ctx=ctx,
    extras=[f"fix pattern for: {target_result.target.path}"],
)

# Combine both into the fix prompt
extra={
    "retrieved_context": wrapper_block,
    "retrieved_siblings": wrapper_block,
    "skeleton_reference": skeleton_block,  # NEW
    ...
}
```

The fix model now sees:
1. The failing file (current contents)
2. The test output (error + traceback)
3. Sibling service context (wrapper retrieval)
4. **Reference implementation patterns** (skeleton retrieval) — shows
   the model what "correct" looks like for this pattern

This is especially valuable when the AI generated code that diverges
from the skeleton's patterns — the fix model can see the reference and
align back to it.

### 6.5 Configuration

```bash
# .env or shell environment
OLLAMA_FIX_MODEL=qwen2.5-coder:32b     # dedicated fix model
OLLAMA_MODEL=qwen3-coder:30b            # generation model (unchanged)

# Or override per-run:
OLLAMA_FIX_MODEL=qwen3-coder:30b _bin/skel-gen-ai myproject  # fast fix
```

New config field in `OllamaConfig`:

```python
# config.py
DEFAULT_OLLAMA_FIX_MODEL = "qwen2.5-coder:32b"

@dataclass
class OllamaConfig:
    model: str = DEFAULT_OLLAMA_MODEL           # generation
    fix_model: str = DEFAULT_OLLAMA_FIX_MODEL   # test-fix loop
    ...

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        ...
        return cls(
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            fix_model=os.environ.get(
                "OLLAMA_FIX_MODEL", DEFAULT_OLLAMA_FIX_MODEL
            ),
            ...
        )

    def for_fix(self) -> "OllamaConfig":
        """Return a config variant using the fix model."""
        return OllamaConfig(
            model=self.fix_model,
            base_url=self.base_url,
            timeout=min(self.timeout, 300),  # shorter timeout for fixes
            temperature=0.1,  # lower temp for deterministic patches
        )
```

### 6.6 Fix Prompt Enhancement

When the fix model is a qwen3 variant, prepend `/no_think` to
suppress chain-of-thought:

```python
# In _ask_ollama_to_fix or agent.fix_target:
fix_cfg = self._ollama_cfg.for_fix()
system_prompt = _FIX_SYSTEM_PROMPT
if "qwen3" in fix_cfg.model.lower():
    system_prompt = "/no_think\n" + system_prompt
```

### 6.7 Expected Impact

| Metric | Before (same model) | After (dedicated fix model) |
|--------|---------------------|---------------------------|
| Fix success per iteration | ~60% | ~73% (qwen2.5-coder) |
| Avg iterations to green | 3-5 | 2-3 |
| Time per fix iteration | 60-120s (30B thinking) | 30-60s (32B, no think) |
| Total fix-loop time | 5-10 min | 2-5 min |
| Context quality | Wrapper siblings only | Wrapper + skeleton reference |

---

## Operator Commands

After implementation, the following should work:

```bash
# Silent mode (current default — no change)
_bin/skel-gen-ai myproject

# Phase timers + heartbeat
_bin/skel-gen-ai -v myproject

# Full detail: scores, token counts, throughput, chunk stats
_bin/skel-gen-ai -vv myproject

# Maximum transparency: dumps everything to .ai/debug/
_bin/skel-gen-ai -vvv myproject

# Just see RAG stats without running Ollama
_bin/skel-gen-ai -vvv --dry-run myproject

# Enable LLM reranking with full observability
SKEL_RAG_USE_LLM_RERANKER=1 _bin/skel-gen-ai -vv myproject

# Use a better embedding model
SKEL_RAG_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code \
  _bin/skel-gen-ai -v myproject

# Use dedicated fix model (separate from generation model)
OLLAMA_FIX_MODEL=qwen2.5-coder:32b \
OLLAMA_MODEL=qwen3-coder:30b \
  _bin/skel-gen-ai -v myproject

# Fast fix iterations (qwen3 MoE speed, thinking disabled)
OLLAMA_FIX_MODEL=qwen3-coder:30b _bin/skel-gen-ai myproject
```

---

## Success Criteria

1. `skel-gen-ai -vvv --dry-run` produces a full debug dump showing
   corpus stats, per-target retrieval scores, and context utilization
   — with zero Ollama calls.
2. Every RAG component (embedder, indexer, chunker, retriever, LLM)
   reports its timing at `-v` level.
3. Retrieval scores are visible at `-vv` — developers can see WHY
   certain chunks were selected and tune prompts accordingly.
4. Metrics export (JSON) enables automated A/B comparisons between
   models, chunk strategies, and reranking approaches.
5. No performance regression when verbose=0 (metrics collection has
   negligible overhead via conditional checks).
6. `OLLAMA_FIX_MODEL` controls the fix-loop model independently from
   `OLLAMA_MODEL`. Default: `qwen2.5-coder:32b`.
7. Fix-loop retrieves from both wrapper siblings AND skeleton reference
   corpus, giving the fix model reference patterns to align against.
8. Thinking mode is automatically suppressed (via `/no_think`) when
   the fix model is a qwen3 variant.
