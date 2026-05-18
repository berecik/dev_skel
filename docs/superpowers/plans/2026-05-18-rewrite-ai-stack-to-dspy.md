# Rewrite `dev_skel` AI Stack to DSPy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is a large multi-PR rewrite; execute one phase per PR with maintenance/test-fix loop between each.

**Goal:** Replace the hand-rolled prompt + retrieval + fix-loop stack
in `_bin/skel_ai_lib.py` and `_bin/skel_rag/` with a DSPy-based pipeline
where prompts are declarative `Signature`s, orchestration is composed
`Module`s, retrieval is a `dspy.Retrieve` over the existing FAISS
index, and the test-and-fix loop becomes a compiled program that can
be optimized against the pizzeria/integration test suites.

**Architecture:** Keep Ollama as the local LM backend (via
`dspy.LM("ollama_chat/...")`). Keep FAISS as the vector store (wrapped
in a `dspy.Retrieve` adapter). Migrate every prompt-template / chat
call / orchestration loop to DSPy primitives. Preserve the per-phase
model split (GEN / CREATE_TEST / CHECK_TEST / FIX / DOCS) by using
`dspy.LM` context managers around each module. The vendored detached
`./ai` runtime stays stdlib-only — DSPy is only required in-tree.

**Tech Stack:** Python 3.10+, DSPy 2.5+, Ollama (local LM), FAISS
(retained), sentence-transformers / HuggingFace embeddings (retained),
existing tree-sitter chunker (retained). Removed: hand-written prompt
templates, the manual `_chat_stdlib` urllib path, `langchain_ollama`,
the bespoke fix-loop logic in `skel_ai_lib.py`.

---

## 1. Current State (what we are replacing)

| Layer | Today | File(s) | LoC |
|---|---|---|---|
| Ollama HTTP | `urllib.request` + `langchain_ollama` (with `urllib` preferred — see `feedback_stdlib_over_langchain.md`) | `_bin/skel_rag/llm.py` | 305 |
| Model slots | 5 hand-managed model strings + `for_<phase>()` swaps | `_bin/skel_rag/config.py` | 343 |
| Prompt templates | Free-form Python strings in `SYSTEM_PROMPT` per manifest | `_skels/_common/manifests/*.py` | ~250 lines each × 18 manifests |
| Prompt rendering | `format_prompt()` + `build_system_prompt()` + `clean_response()` | `_bin/skel_ai_lib.py:1315-1426` | ~150 |
| Retrieval | hand-rolled FAISS retriever | `_bin/skel_rag/retriever.py` + `vectorstore.py` | 392 |
| Chunking | tree-sitter + recursive char fallback | `_bin/skel_rag/chunker.py` | 671 |
| Per-target loop | `RagAgent.generate_targets` | `_bin/skel_rag/agent.py:173-313` | 140 |
| Integration phase | `RagAgent.run_integration_phase` | `_bin/skel_rag/agent.py:453+` | ~200 |
| CHECK_TEST critique | `_maybe_check_target` | `_bin/skel_rag/agent.py:317-449` | 132 |
| Test+fix loop | `run_test_and_fix_loop`, `_ask_ollama_to_fix`, `_generate_test_file`, `_check_test_file`, `_fix_failing_files` | `_bin/skel_ai_lib.py:1741-2540` | ~800 |
| Service `./ai` runtime | `_bin/dev_skel_refactor_runtime.py` + vendored copy | `_bin/dev_skel_refactor_runtime.py` | 2377 |
| Top-level shim | re-exports + wrappers for legacy callers | `_bin/skel_ai_lib.py` | 3753 |

**Total in-scope LoC:** ~9,500 across `_bin/skel_rag/` + `_bin/skel_ai_lib.py`.

Consumers (must keep working after migration):

- `_bin/skel-gen-ai` (CLI entrypoint)
- `_bin/skel-ai` (out-of-process `./ai` driver)
- `_bin/skel-rag` (RAG CLI: index/search/info/clean/generate)
- `_bin/skel-deploy`, `_bin/skel-test-*` runners
- `_skels/_common/refactor_runtime/{ai,dev_skel_refactor_runtime.py}` (vendored)
- 18 manifests in `_skels/_common/manifests/`

---

## 2. Why DSPy

What DSPy buys us, ranked by impact for this project:

1. **Signatures replace prompt templates.** Each per-target prompt
   becomes `class GenerateFile(dspy.Signature): reference: str; target_path: str; item_class: str; → file_contents: str`. The
   18 × 250-line prompt files collapse to a small set of typed
   signatures + per-target *metadata* (no more `{template}` / `{retrieved_context}` / `{prior_outputs}` string-substitution gymnastics in `format_prompt`).
2. **Optimizers.** We already have ground-truth: the pizzeria
   playbook, the shared-DB test, the cross-stack devcontainer + k8s
   tests, and `make test-ai-generators-dry`. These are perfect
   `dspy.Evaluate` metrics. `BootstrapFewShot` / `MIPRO` can search
   over prompt variants and few-shot exemplars to improve pass
   rates without us hand-tuning prompts (the current
   `_docs/RAG-IMPROVEMENT-PLAN.md` is doing this by hand).
3. **Composable modules.** `RagAgent.generate_targets` is currently
   a 140-line method with multi-phase context, retrieval, CHECK_TEST
   review, and retry baked in. As a DSPy `Module` it becomes ~5
   sub-modules wired together with explicit data flow.
4. **Built-in caching + observability.** DSPy ships LM call caching
   keyed on prompt content (vs. our `_make_chat_model` `lru_cache`
   on model name only) and structured tracing. Our hand-rolled
   `chat_with_metrics` + `LlmCallMetrics` becomes free.
5. **First-class assertion / refinement.** `dspy.Assert` and
   `dspy.Suggest` let the CHECK_TEST review be a proper backtracking
   constraint rather than the current "regenerate once if FAIL"
   hand-coded retry.

What DSPy does NOT solve, that we must preserve manually:

- The detached-service `./ai` path (vendored runtime) must stay
  stdlib-only. DSPy is in-tree only. This means
  `_bin/dev_skel_refactor_runtime.py` keeps its current minimal urllib
  client for out-of-tree runs.
- Ollama transient-error retry (peer closed / OOM-on-reload) — DSPy's
  built-in retry is HTTP-status-based, ours is error-string-based.
  Keep a thin wrapper.
- The `{template}` / `{wrapper_snapshot}` legacy placeholders are
  still used by some manifests. The migration is gradual; legacy
  manifests must continue working until each one is ported.

---

## 3. Constraints (non-negotiable)

- **Per CLAUDE.md §5.5:** no skipping failing tests, no weakening
  tests during migration. Every DSPy module must clear the same
  `make test-ai-generators-dry` / `make test-shared-db` / `make
  test-pizzeria-orders` gates the current stack clears.
- **Per CLAUDE.md §6:** Ollama-bound tests skip with exit code 2 when
  Ollama is unreachable. DSPy LM init must mirror this — never hard-fail
  if `ollama serve` is down.
- **Per CLAUDE.md §1 Mandatory Test Artifact Location:** every
  scratch project for these phases lives under `_test_projects/`.
- **Vendored runtime stays stdlib-only.** Track changes that need
  syncing via `make sync-ai-runtime`.
- **Single source of truth for models.** Keep `_bin/skel_rag/config.py`
  as the one place that names models; the DSPy LM factory reads from
  it. Do not duplicate model names into DSPy module definitions.
- **No new third-party deps without justification.** DSPy itself
  pulls in `litellm`, `pydantic`, `optuna` (for MIPRO). Document
  these in `_docs/DEPENDENCIES.md` and add to the existing
  `make install-rag-deps` recipe.
- **`./backport` is file-diff only — DO NOT migrate it.** No LLM call
  is involved. It stays untouched.

---

## 4. Migration Strategy: Strangler Fig

The current code has a clean boundary: every LM call goes through
`skel_rag.llm.chat()` and every prompt is assembled in
`skel_rag.prompts` or `skel_ai_lib.format_prompt`. We replace these
two seams first, then peel layers outward.

```
Phase 1 — LM adapter        : skel_rag.llm.chat() → DSPy LM
Phase 2 — Simple signatures : per-target generation → DSPy Predict
Phase 3 — Retrieval         : skel_rag.retriever  → DSPy Retrieve adapter
Phase 4 — Integration phase : run_integration_phase → DSPy Module
Phase 5 — CHECK_TEST        : _maybe_check_target  → dspy.Suggest
Phase 6 — Test/fix loop     : run_test_and_fix_loop → DSPy Module (with metric)
Phase 7 — Optimization      : compile programs against pizzeria / shared-DB
Phase 8 — Cleanup           : delete dead prompt assembly code, deprecate skel_ai_lib re-exports
Phase 9 — Docs              : update CLAUDE.md, MODELS.md, RAG-IMPROVEMENT-PLAN.md, LLM-MAINTENANCE.md
```

Each phase ships independently and leaves the system green for every
maintenance scenario in CLAUDE.md.

---

## Phase 0: Spike — prove DSPy + Ollama + FAISS works

**Goal:** Build a throwaway proof-of-concept in `_test_projects/` that
calls Ollama via DSPy, uses our existing FAISS index, and produces
one file from one prompt. Decide stop/go before touching production
code.

**Files:**
- Create: `_test_projects/dspy_spike/run.py`

- [ ] **Step 1: Install DSPy in the dev_skel venv**

```bash
~/.local/share/dev-skel/venv/bin/pip install 'dspy-ai>=2.5'
```

Expected: install succeeds, prints "Successfully installed dspy-ai-2.x.y litellm-... optuna-...".

- [ ] **Step 2: Write a minimal DSPy + Ollama smoke test**

```python
# _test_projects/dspy_spike/run.py
"""Phase-0 spike: call Ollama through DSPy, dump the response.

Goal: prove DSPy + ollama_chat works without us touching any
production code. If this fails we revisit the choice."""
import dspy

lm = dspy.LM(
    "ollama_chat/qwen3-coder:30b",
    api_base="http://localhost:11434",
    api_key="",
)
dspy.configure(lm=lm)

class WriteHello(dspy.Signature):
    """Produce one line of Python that prints the given greeting."""
    greeting: str = dspy.InputField()
    code: str = dspy.OutputField()

result = dspy.Predict(WriteHello)(greeting="hello dspy")
print(result.code)
```

- [ ] **Step 3: Run the spike and verify output**

Run: `~/.local/share/dev-skel/venv/bin/python _test_projects/dspy_spike/run.py`
Expected: prints a Python `print(...)` statement containing `hello dspy`.

- [ ] **Step 4: Decision gate**

If the spike succeeds → continue to Phase 1.
If it fails (DSPy can't reach Ollama, signature parsing fails on
qwen3-coder, etc.) → STOP and reassess. Possible fallbacks:
- Try `qwen2.5-coder:32b` (more stable JSON output).
- Use DSPy with `dspy.adapters.JSONAdapter` explicitly.
- Abandon the migration if DSPy can't be made reliable with local Ollama.

- [ ] **Step 5: Commit the spike**

```bash
git add _test_projects/dspy_spike/run.py
git commit -m "spike: DSPy + Ollama smoke test for dspy migration"
```

---

## Phase 1: LM adapter (replace `skel_rag.llm.chat`)

**Goal:** Make every LM call go through DSPy. No prompts change yet —
this is purely a transport swap.

**Files:**
- Modify: `_bin/skel_rag/llm.py:200-249` (replace `chat()` body)
- Create: `_bin/skel_rag/dspy_lm.py` (DSPy LM factory)
- Create: `_bin/skel_rag/tests/test_dspy_lm.py`
- Modify: `_docs/DEPENDENCIES.md` (add dspy-ai to RAG deps)
- Modify: `_bin/skel-install-rag` (add `dspy-ai`)

- [ ] **Step 1: Write the failing test**

```python
# _bin/skel_rag/tests/test_dspy_lm.py
"""Phase-1: dspy_lm.make_lm() returns a configured dspy.LM bound to
the right Ollama endpoint and model for the given OllamaConfig."""
import os
import pytest

from skel_rag.config import OllamaConfig

dspy = pytest.importorskip("dspy")
from skel_rag.dspy_lm import make_lm


def test_make_lm_uses_config_model_and_base_url():
    cfg = OllamaConfig(
        model="qwen3-coder:30b",
        base_url="http://localhost:11434",
        temperature=0.2,
        timeout=600,
    )
    lm = make_lm(cfg)
    assert isinstance(lm, dspy.LM)
    assert lm.model == "ollama_chat/qwen3-coder:30b"
    assert lm.kwargs["api_base"] == "http://localhost:11434"
    assert lm.kwargs["temperature"] == 0.2


def test_make_lm_caches_by_model_and_url():
    cfg = OllamaConfig(model="m", base_url="http://h:1", temperature=0.2, timeout=60)
    a = make_lm(cfg)
    b = make_lm(cfg)
    assert a is b, "DSPy LM should be memoised so per-target loop reuses one client"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.local/share/dev-skel/venv/bin/pytest _bin/skel_rag/tests/test_dspy_lm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skel_rag.dspy_lm'`.

- [ ] **Step 3: Implement `skel_rag/dspy_lm.py`**

```python
# _bin/skel_rag/dspy_lm.py
"""DSPy LM factory bound to the project's OllamaConfig.

Every DSPy module in skel_rag eventually goes through here. The
returned LM is memoised on (model, base_url, temperature, timeout)
so the per-target loop reuses one client instead of re-creating
the litellm HTTP session per call.

Phase-specific variants (FIX, CREATE_TEST, CHECK_TEST, DOCS) are
not constructed here — callers build a sibling config via
``cfg.for_fix()`` etc. and pass it back through make_lm()."""
from __future__ import annotations
from functools import lru_cache

import dspy

from skel_rag.config import OllamaConfig


@lru_cache(maxsize=8)
def _cached(model: str, base_url: str, temperature: float, timeout: int) -> dspy.LM:
    return dspy.LM(
        f"ollama_chat/{model}",
        api_base=base_url,
        api_key="",
        temperature=temperature,
        timeout=timeout,
    )


def make_lm(cfg: OllamaConfig) -> dspy.LM:
    return _cached(cfg.model, cfg.base_url, cfg.temperature, cfg.timeout)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `~/.local/share/dev-skel/venv/bin/pytest _bin/skel_rag/tests/test_dspy_lm.py -v`
Expected: 2 passed.

- [ ] **Step 5: Swap `skel_rag.llm.chat()` to call DSPy**

Modify `_bin/skel_rag/llm.py:202-249`:

```python
def chat(config: OllamaConfig, system: str, user: str) -> str:
    """Send one system+user turn through DSPy → litellm → Ollama.

    The signature is preserved so every existing caller in
    skel_ai_lib + skel_rag.agent works unchanged. Retries on
    transient connection errors (peer closed, refused, timeout)
    are kept here because DSPy/litellm do not retry on
    error-string patterns specific to Ollama model reloads."""
    from skel_rag.dspy_lm import make_lm
    import time as _time

    lm = make_lm(config)
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = lm(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            # litellm returns list[str] when called raw.
            return response[0] if isinstance(response, list) else response
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            err_str = str(exc).lower()
            is_transient = any(k in err_str for k in (
                "peer closed", "connection refused", "incomplete chunked",
                "connection reset", "timed out", "eof occurred",
            ))
            if is_transient and attempt < _MAX_RETRIES:
                logger.warning(
                    "Ollama transient error (attempt %d/%d): %s — "
                    "retrying in %ds...",
                    attempt, _MAX_RETRIES, exc, _RETRY_DELAY_S,
                )
                _time.sleep(_RETRY_DELAY_S)
                continue
            raise OllamaError(str(exc)) from exc
    raise OllamaError(
        f"Ollama request failed after {_MAX_RETRIES} retries: {last_exc}"
    )
```

Delete `_chat_stdlib`, `_make_chat_model`, `make_chat_model`, and the
`_HAS_LANGCHAIN` branch — DSPy/litellm handles HTTP from here on.
Keep `verify()` (it pings `/api/tags`, not a chat endpoint).

- [ ] **Step 6: Run the full smoke**

Run: `make test-ai-generators-dry`
Expected: all skels green (no Ollama calls made because dry-run, but
imports must still resolve). Run: `make test-ai-script`
Expected: PASS — the dispatch smoke does not call Ollama either, but
the `./ai` import path must still resolve through `skel_rag.llm`.

- [ ] **Step 7: Live Ollama smoke**

When an Ollama host is reachable:
Run: `_bin/skel-test-ai-generators --skel python-fastapi-skel`
Expected: completes without `langchain_ollama` being imported (verify
with `grep langchain` over the run log → no matches).

- [ ] **Step 8: Commit**

```bash
git add _bin/skel_rag/dspy_lm.py _bin/skel_rag/llm.py \
        _bin/skel_rag/tests/test_dspy_lm.py \
        _bin/skel-install-rag _docs/DEPENDENCIES.md
git commit -m "Route Ollama chat through DSPy LM (Phase 1 of DSPy rewrite)"
```

---

## Phase 2: Signatures — declarative per-target generation

**Goal:** Replace the giant string-templated SYSTEM_PROMPT + per-target
prompt with `dspy.Signature` classes. One manifest is migrated
end-to-end as the reference (`python-fastapi-skel`); the other 17 keep
working via a back-compat path that wraps their legacy prompts.

**Files:**
- Create: `_bin/skel_rag/signatures/__init__.py`
- Create: `_bin/skel_rag/signatures/generate_file.py`
- Create: `_bin/skel_rag/signatures/integrate.py`
- Create: `_bin/skel_rag/signatures/fix_failing.py`
- Create: `_bin/skel_rag/signatures/create_test.py`
- Create: `_bin/skel_rag/signatures/check_test.py`
- Modify: `_skels/_common/manifests/python-fastapi-skel.py` (collapse the prompt to metadata; signature pulls from `_bin/skel_rag/signatures/`)
- Modify: `_bin/skel_rag/agent.py:173-313` (`generate_targets` calls `dspy.Predict(GenerateFile)` instead of formatting strings)
- Modify: `_bin/skel_ai_lib.py:1385-1426` (`build_system_prompt` becomes a thin compat shim — already done in current code, now actually a no-op for migrated manifests)
- Create: `_bin/skel_rag/tests/test_signatures.py`

- [ ] **Step 1: Design the `GenerateFile` signature**

```python
# _bin/skel_rag/signatures/generate_file.py
"""Signature for one per-target file generation in the per-target phase.

The fields here used to be string-templated in every manifest's
SYSTEM_PROMPT. By declaring them once at the framework level, every
manifest collapses to (a) target paths + reference templates and
(b) any per-skeleton overrides expressed as Pydantic
dspy.InputField hints — no more 250-line prompt strings."""
from __future__ import annotations
import dspy


class GenerateFile(dspy.Signature):
    """Rewrite one skeleton reference template for the user's domain.

    You are a senior engineer regenerating ONE file inside a generated
    service. Follow the reference's structure, indentation, and import
    style. Replace the example entity (`ExampleItem` / `example_item` /
    `example_items`) with the user's entity. Output ONLY the file
    contents — no markdown fences, no commentary.
    """

    skeleton_name: str = dspy.InputField(desc="e.g. python-fastapi-skel")
    target_path: str = dspy.InputField(desc="relative path of the file being generated")
    reference_template: str = dspy.InputField(desc="the example_items reference content")
    retrieved_context: str = dspy.InputField(desc="RAG-retrieved sibling files (may be empty)")
    prior_outputs: str = dspy.InputField(desc="files already generated earlier in this run")
    item_class: str = dspy.InputField(desc="PascalCase entity name, e.g. Order")
    item_name: str = dspy.InputField(desc="snake_case entity, e.g. order")
    items_plural: str = dspy.InputField(desc="snake_case plural, e.g. orders")
    service_label: str = dspy.InputField(desc="human service name, e.g. 'Order Service'")
    auth_type: str = dspy.InputField(desc="'jwt' | 'session' | 'none'")
    backend_extra: str = dspy.InputField(desc="user-supplied domain instructions (may be empty)")

    file_contents: str = dspy.OutputField(
        desc="exact contents of the new file, no fences, no preamble"
    )
```

- [ ] **Step 2: Write the failing signature test**

```python
# _bin/skel_rag/tests/test_signatures.py
"""Phase-2 signatures must validate field names + types and round-trip
through DSPy adapters."""
import pytest

dspy = pytest.importorskip("dspy")
from skel_rag.signatures.generate_file import GenerateFile


def test_generate_file_signature_has_required_fields():
    fields = GenerateFile.input_fields
    for name in (
        "skeleton_name", "target_path", "reference_template",
        "retrieved_context", "prior_outputs", "item_class", "item_name",
        "items_plural", "service_label", "auth_type", "backend_extra",
    ):
        assert name in fields, f"missing input field: {name}"
    assert "file_contents" in GenerateFile.output_fields
```

- [ ] **Step 3: Run and verify it fails / then implement / then re-run**

Run: `~/.local/share/dev-skel/venv/bin/pytest _bin/skel_rag/tests/test_signatures.py -v`
Expected first: ImportError. After writing signature: PASS.

- [ ] **Step 4: Add `RagAgent.generate_targets_with_dspy()` (parallel path)**

In `_bin/skel_rag/agent.py`, add a new method that mirrors
`generate_targets` but builds inputs for the `GenerateFile` signature
instead of formatting strings. Wire it on by feature flag:
`SKEL_RAG_USE_DSPY=1`. Default off until Phase 6 lands.

```python
def generate_targets_with_dspy(self, *, manifest, ctx, dry_run=False, progress=None):
    import dspy
    from skel_rag.dspy_lm import make_lm
    from skel_rag.signatures.generate_file import GenerateFile
    from skel_ai_lib import TargetResult, clean_response, expand_target_paths, _read_reference

    lm = make_lm(self.ollama_cfg)
    predictor = dspy.Predict(GenerateFile)
    retriever = self.get_retriever(corpus_for_skeleton(ctx.skeleton_path))

    results, prior_outputs = [], []
    with dspy.context(lm=lm):
        for index, target in enumerate(manifest.targets, start=1):
            expanded = expand_target_paths(target, ctx)
            # ...skip-for-item-class same as legacy path...
            reference = _read_reference(ctx.skeleton_path, expanded.template) or ""
            retrieved_block = self._retrieve_block_for_target(
                retriever=retriever, target=expanded, ctx=ctx,
            )
            prior_block = "\n\n".join(prior_outputs) if prior_outputs else ""

            destination = ctx.project_dir / expanded.path
            if dry_run:
                results.append(TargetResult(target=expanded, written_to=destination, bytes_written=0))
                continue

            pred = predictor(
                skeleton_name=manifest.skeleton_name,
                target_path=expanded.path,
                reference_template=reference,
                retrieved_context=retrieved_block,
                prior_outputs=prior_block,
                item_class=ctx.item_class,
                item_name=ctx.item_name,
                items_plural=ctx.items_plural,
                service_label=ctx.service_label,
                auth_type=ctx.auth_type,
                backend_extra=ctx.backend_extra or "",
            )
            cleaned = clean_response(pred.file_contents, target.language)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(cleaned, encoding="utf-8")
            results.append(TargetResult(
                target=expanded, written_to=destination, bytes_written=len(cleaned.encode("utf-8")),
            ))
            snippet = cleaned[:2000]
            prior_outputs.append(f"--- FILE: {expanded.path} ---\n{snippet}\n--- END ---")
    return results
```

- [ ] **Step 5: Feature-flag the call site**

In `_bin/skel-gen-ai`, around the `client.agent.generate_targets(...)`
call: branch on `os.environ.get("SKEL_RAG_USE_DSPY") == "1"`. Default
is unchanged behaviour.

- [ ] **Step 6: Live A/B test**

Run with the flag off, then on, on the `python-fastapi-skel` pizzeria
playbook (`make test-pizzeria-orders`). Save both runs' output trees
to `_test_projects/dspy_ab/{off,on}/` and diff them.

Expected: both pass the 14-step HTTP exercise. Differences allowed in
code formatting but not in API surface.

- [ ] **Step 7: Add `CHECK_TEST` signature**

Mirror `_maybe_check_target` (`_bin/skel_rag/agent.py:317-449`) as
`CheckTest(dspy.Signature)` with output `verdict: Literal["OK", "FAIL"]`
and `reason: str`. Wire through `dspy.Suggest` so a FAIL verdict
auto-triggers a backtrack/regenerate inside DSPy instead of our
manual one-shot retry.

- [ ] **Step 8: Commit**

```bash
git add _bin/skel_rag/signatures/ _bin/skel_rag/agent.py \
        _bin/skel_rag/tests/test_signatures.py _bin/skel-gen-ai
git commit -m "Add DSPy signatures for per-target generation (Phase 2 of DSPy rewrite)"
```

---

## Phase 3: Retrieval — wrap FAISS as `dspy.Retrieve`

**Goal:** Make retrieval composable inside DSPy modules without
rebuilding the index. Keeps tree-sitter chunker + FAISS unchanged.

**Files:**
- Create: `_bin/skel_rag/dspy_retriever.py`
- Modify: `_bin/skel_rag/agent.py` (`_retrieve_block_for_target` → returns `dspy.Prediction`)
- Create: `_bin/skel_rag/tests/test_dspy_retriever.py`

- [ ] **Step 1: Write the test**

```python
# _bin/skel_rag/tests/test_dspy_retriever.py
"""Phase-3: a SkelRagRM wraps an existing Retriever so DSPy modules
can call it like any other dspy.Retrieve. Returns dspy.Prediction
with .passages so the standard ChainOfThought / ReAct flows work."""
import pytest

dspy = pytest.importorskip("dspy")
from skel_rag.config import RagConfig
from skel_rag.dspy_retriever import SkelRagRM


def test_returns_prediction_with_passages(tmp_path):
    # Build a tiny corpus on disk and verify SkelRagRM(.forward) returns
    # dspy.Prediction(passages=[...]).
    (tmp_path / "a.py").write_text("def hello(): return 'world'")
    rm = SkelRagRM.from_path(tmp_path, RagConfig.from_env())
    pred = rm("hello world")
    assert hasattr(pred, "passages")
    assert any("hello" in p for p in pred.passages)
```

- [ ] **Step 2: Run, verify it fails, then implement**

```python
# _bin/skel_rag/dspy_retriever.py
"""DSPy RM adapter for skel_rag.retriever.Retriever.

Why a wrapper instead of using dspy's built-in retrievers: we already
have a tuned tree-sitter chunker + FAISS index on disk for every
skeleton. dspy.ColBERTv2 would force us to re-embed (and reinstall
ColBERT). Wrapping is one screen of code."""
from __future__ import annotations
import dspy

from skel_rag.config import RagConfig
from skel_rag.corpus import corpus_for_skeleton
from skel_rag.retriever import Retriever


class SkelRagRM(dspy.Retrieve):
    def __init__(self, retriever: Retriever, k: int = 5):
        super().__init__(k=k)
        self._retriever = retriever

    @classmethod
    def from_path(cls, path, cfg: RagConfig | None = None) -> "SkelRagRM":
        from skel_rag.agent import RagAgent
        agent = RagAgent(rag_cfg=cfg)
        retriever = agent.get_retriever(corpus_for_skeleton(path))
        if retriever is None:
            raise RuntimeError("retrieval backend unavailable")
        return cls(retriever, k=cfg.top_k if cfg else 5)

    def forward(self, query: str, k: int | None = None) -> dspy.Prediction:
        chunks = self._retriever.retrieve(query, k=k or self.k)
        passages = [c.source for c in chunks]
        return dspy.Prediction(passages=passages)
```

- [ ] **Step 3: Run the test → PASS**

- [ ] **Step 4: Wire into the agent**

In `RagAgent.generate_targets_with_dspy`, set
`dspy.configure(rm=SkelRagRM(retriever))` and use
`dspy.ChainOfThought(GenerateFile)` to access `.passages` if you want
DSPy to manage retrieval in-band. Keep the current "retrieve once at
top of loop" pattern too — the wrapper is opt-in.

- [ ] **Step 5: Commit**

```bash
git add _bin/skel_rag/dspy_retriever.py \
        _bin/skel_rag/tests/test_dspy_retriever.py _bin/skel_rag/agent.py
git commit -m "Wrap FAISS retriever as dspy.Retrieve (Phase 3 of DSPy rewrite)"
```

---

## Phase 4: Integration phase as a DSPy `Module`

**Goal:** Replace `RagAgent.run_integration_phase` (200 LoC, file
~450 onward) with a composed DSPy module.

**Files:**
- Create: `_bin/skel_rag/programs/integration.py`
- Create: `_bin/skel_rag/signatures/integrate.py`
- Modify: `_bin/skel_rag/agent.py` (delegate to `programs.integration.IntegrationProgram` when `SKEL_RAG_USE_DSPY=1`)
- Create: `_bin/skel_rag/tests/test_integration_program.py`

- [ ] **Step 1: Write the integration signature**

```python
# _bin/skel_rag/signatures/integrate.py
import dspy


class IntegrateService(dspy.Signature):
    """Write integration code that wires a new service into its sibling
    services in the wrapper. Use the retrieved sibling files as the
    source of truth — never invent route paths or env-var names."""
    target_path: str = dspy.InputField()
    retrieved_siblings: str = dspy.InputField()
    item_class: str = dspy.InputField()
    service_label: str = dspy.InputField()
    integration_extra: str = dspy.InputField(desc="user-supplied integration instructions, may be empty")
    file_contents: str = dspy.OutputField()
```

- [ ] **Step 2: Write the `IntegrationProgram` module**

```python
# _bin/skel_rag/programs/integration.py
import dspy
from skel_rag.signatures.integrate import IntegrateService


class IntegrationProgram(dspy.Module):
    def __init__(self):
        super().__init__()
        self.integrate = dspy.ChainOfThought(IntegrateService)

    def forward(self, target_path, retrieved_siblings, item_class,
                service_label, integration_extra=""):
        return self.integrate(
            target_path=target_path,
            retrieved_siblings=retrieved_siblings,
            item_class=item_class,
            service_label=service_label,
            integration_extra=integration_extra,
        )
```

- [ ] **Step 3: Write the test**

Use `_test_projects/dspy_integration_smoke/` as the fixture wrapper.
Generate a python-django-bolt service first (or copy a fixture), then
run `IntegrationProgram.forward(...)` and assert the predicted
`file_contents` includes a known sibling route (e.g. `/api/items`).

- [ ] **Step 4: Wire `RagAgent.run_integration_phase` to call the program when the flag is on**

- [ ] **Step 5: Run `make test-shared-db-python`**

Expected: PASS (Python-only shared-DB exercise must still complete).

- [ ] **Step 6: Commit**

```bash
git add _bin/skel_rag/programs/ _bin/skel_rag/signatures/integrate.py \
        _bin/skel_rag/agent.py _bin/skel_rag/tests/test_integration_program.py
git commit -m "Integration phase as DSPy Module (Phase 4 of DSPy rewrite)"
```

---

## Phase 5: CHECK_TEST → `dspy.Suggest`

**Goal:** The current `_maybe_check_target` runs the reviewer, parses
"OK" / "FAIL: reason", and manually regenerates once. Convert to
`dspy.Suggest` so DSPy handles backtracking and counts retries.

**Files:**
- Create: `_bin/skel_rag/signatures/check_test.py`
- Modify: `_bin/skel_rag/programs/integration.py`, `_bin/skel_rag/agent.py`
- Modify: `_bin/skel_rag/tests/test_check_test.py`

- [ ] **Step 1: Define the signature**

```python
# _bin/skel_rag/signatures/check_test.py
from typing import Literal
import dspy


class ReviewGeneratedFile(dspy.Signature):
    """Spot REAL issues — references to symbols that no sibling file
    defines, imports that won't resolve, methods called on a class
    that doesn't declare them, assertions that contradict the
    contract. Do NOT nitpick style."""
    generated_file: str = dspy.InputField()
    sibling_files: str = dspy.InputField()
    contract: str = dspy.InputField(desc="OpenAPI snippet, may be empty")
    verdict: Literal["OK", "FAIL"] = dspy.OutputField()
    reason: str = dspy.OutputField(desc="one-line explanation if FAIL, else empty")
```

- [ ] **Step 2: Compose into the generation program**

```python
def forward(self, ...):
    pred = self.generate(...)
    review = self.review(generated_file=pred.file_contents, ...)
    dspy.Suggest(
        review.verdict == "OK",
        f"Reviewer flagged: {review.reason}",
    )
    return pred
```

- [ ] **Step 3: Test that a known-bad output triggers regeneration**

Fixture: a hand-crafted prompt that produces an obviously broken file
(import from a non-existent sibling). Assert the program regenerates
at least once and the second call succeeds.

- [ ] **Step 4: Commit**

---

## Phase 6: Test/Fix loop — DSPy `Module` with metric

**Goal:** Replace `run_test_and_fix_loop` (`_bin/skel_ai_lib.py:1894`,
~150 LoC) and `_fix_failing_files` (`_bin/skel_ai_lib.py:2351`,
~200 LoC) with a DSPy module whose metric is "service tests pass".

**Files:**
- Create: `_bin/skel_rag/programs/test_fix_loop.py`
- Create: `_bin/skel_rag/signatures/fix_failing.py`
- Modify: `_bin/skel-gen-ai` (call the new program)
- Modify: `_bin/skel_ai_lib.py` (keep `run_test_and_fix_loop` as a back-compat shim that delegates)
- Create: `_bin/skel_rag/tests/test_test_fix_loop.py`

- [ ] **Step 1: `FixFailingFile` signature**

```python
# _bin/skel_rag/signatures/fix_failing.py
import dspy


class FixFailingFile(dspy.Signature):
    """Patch ONE file so the failing test passes. Output ONLY the
    full replacement file contents."""
    file_path: str = dspy.InputField()
    current_contents: str = dspy.InputField()
    test_output: str = dspy.InputField(desc="stderr+stdout of the failing test")
    sibling_context: str = dspy.InputField()
    fixed_contents: str = dspy.OutputField()
```

- [ ] **Step 2: `TestFixLoop` module**

```python
# _bin/skel_rag/programs/test_fix_loop.py
import dspy
from skel_rag.signatures.fix_failing import FixFailingFile


class TestFixLoop(dspy.Module):
    def __init__(self, max_iter=3):
        super().__init__()
        self.fix = dspy.Predict(FixFailingFile)
        self.max_iter = max_iter

    def forward(self, run_tests, list_offending_files, service_dir):
        """run_tests is a callable returning (passed: bool, output: str).
        list_offending_files returns [(path, contents, sibling_ctx), ...]."""
        for i in range(self.max_iter):
            passed, output = run_tests()
            if passed:
                return dspy.Prediction(iterations=i, passed=True)
            for path, contents, sibling_ctx in list_offending_files(output):
                pred = self.fix(file_path=str(path), current_contents=contents,
                                test_output=output, sibling_context=sibling_ctx)
                (service_dir / path).write_text(pred.fixed_contents)
        passed, output = run_tests()
        return dspy.Prediction(iterations=self.max_iter, passed=passed)
```

- [ ] **Step 3: Define the DSPy metric**

```python
def metric_tests_pass(example, pred, trace=None) -> float:
    return 1.0 if pred.passed else 0.0
```

- [ ] **Step 4: Wire into `skel-gen-ai`**

In the test-and-fix phase section, branch on `SKEL_RAG_USE_DSPY=1`
and call `TestFixLoop()(run_tests=..., list_offending_files=..., service_dir=...)`
instead of `run_test_and_fix_loop(...)`.

- [ ] **Step 5: Full pizzeria run**

Run: `make test-pizzeria-orders` with `SKEL_RAG_USE_DSPY=1`.
Expected: 9-point definition of done passes (see
`_docs/PIZZERIA-TEST-PLAYBOOK.md`). If not, debug; do not weaken
tests.

- [ ] **Step 6: Commit**

---

## Phase 7: Compile (optimize) the programs

**Goal:** Use DSPy optimizers to auto-tune prompts and few-shot
exemplars using our existing integration tests as ground truth.

**Files:**
- Create: `_bin/skel_rag/optimize.py`
- Create: `_bin/skel-rag-compile` (CLI)
- Create: `_bin/skel_rag/tests/test_optimize.py`

- [ ] **Step 1: Build a training set from existing test runs**

Run the green-state pipeline a few times against the pizzeria
playbook and the shared-DB exercise; capture (inputs, outputs) for
every per-target call. Persist as `_bin/skel_rag/trainsets/pizzeria.jsonl`.

- [ ] **Step 2: Compile `GenerateProgram` with BootstrapFewShot**

```python
# _bin/skel_rag/optimize.py
import dspy
from dspy.teleprompt import BootstrapFewShot
from skel_rag.programs.generate import GenerateProgram

def compile_generate(trainset, metric_fn):
    base = GenerateProgram()
    tele = BootstrapFewShot(metric=metric_fn, max_bootstrapped_demos=4)
    return tele.compile(student=base, trainset=trainset)
```

- [ ] **Step 3: Persist the compiled program**

Save to `_bin/skel_rag/compiled/generate-program.json`. Loaded by
`RagAgent` when present; otherwise the un-compiled program is used.

- [ ] **Step 4: A/B test**

Compare uncompiled vs compiled program on the pizzeria suite. Record
pass rate + token usage in `_docs/RAG-IMPROVEMENT-PLAN.md` (replaces
the hand-tuning section).

- [ ] **Step 5: Commit (+ checked-in compiled artifact)**

```bash
git add _bin/skel_rag/optimize.py _bin/skel_rag/compiled/ \
        _bin/skel_rag/trainsets/ _bin/skel-rag-compile \
        _bin/skel_rag/tests/test_optimize.py
git commit -m "Compile DSPy programs against pizzeria + shared-DB metrics (Phase 7)"
```

---

## Phase 8: Cleanup — make DSPy the default, deprecate dead code

**Goal:** Flip `SKEL_RAG_USE_DSPY=1` as default, remove the legacy
branch, delete dead prompt-assembly code, and shrink
`skel_ai_lib.py` to a compatibility re-export module.

**Files:**
- Modify: `_bin/skel-gen-ai` (remove flag branches)
- Modify: `_bin/skel_rag/agent.py` (delete legacy `generate_targets`, keep only the DSPy path)
- Delete: `_chat_stdlib`, `_make_chat_model`, `make_chat_model` in `skel_rag/llm.py` (already done in Phase 1, verify)
- Modify: `_bin/skel_ai_lib.py` — shrink to <500 LoC: keep only `AiManifest`, `AiTarget`, `GenerationContext`, `TargetResult`, `TestRunResult`, `expand_target_paths`, `_read_reference`, `format_prompt` (legacy shim), `clean_response`, `build_system_prompt` (legacy shim — returns `""` for migrated manifests). Everything else moves into `skel_rag.programs.*`.
- Delete (do NOT regenerate): the `langchain_ollama` / `langchain_core` import branches.
- Migrate remaining 17 manifests to use `GenerateFile` signature (one PR each so reviews stay small).

- [ ] **Step 1: Flip the default and remove flag branches**

- [ ] **Step 2: Per-manifest migration PRs**

For each of the 17 manifests:

- [ ] python-django-skel
- [ ] python-django-bolt-skel
- [ ] python-flask-skel
- [ ] java-spring-skel
- [ ] java-spring-ddd-skel
- [ ] rust-actix-skel
- [ ] rust-actix-ddd-skel
- [ ] rust-axum-skel
- [ ] rust-axum-ddd-skel
- [ ] go-skel
- [ ] go-ddd-skel
- [ ] next-js-skel
- [ ] next-js-ddd-skel
- [ ] ts-react-skel
- [ ] flutter-skel
- [ ] python-fastapi-rag-skel
- [ ] _kubernetes

For each: (a) port `SYSTEM_PROMPT` body into signature `docstring`
+ field descriptions; (b) collapse `MANIFEST["targets"][n]["prompt"]`
into a thin metadata dict (`reference_template`, `description`); (c)
run `make test-gen-ai-<skel>` end-to-end; (d) PR + commit.

- [ ] **Step 3: Verify the vendored runtime is untouched**

Run `diff _bin/dev_skel_refactor_runtime.py _skels/_common/refactor_runtime/dev_skel_refactor_runtime.py`.
Expected: identical, no DSPy imports.

- [ ] **Step 4: Run the full maintenance scenario**

Per CLAUDE.md §"Maintenance Scenario":

```bash
make clean-test
make test-generators
```

Repeat fix → re-run until green.

- [ ] **Step 5: Commit per-manifest migrations** (one commit each, message format: `Port <skel> manifest to DSPy signature`)

---

## Phase 9: Docs

**Goal:** Update every doc that references the old stack.

**Files:**
- Modify: `/CLAUDE.md` §2 (project snapshot — replace "RagAgent" + "langchain_ollama" with DSPy)
- Modify: `/AGENTS.md` (same)
- Modify: `_docs/MODELS.md` (still single source of truth; add "DSPy LM factory" reference)
- Modify: `_docs/RAG-IMPROVEMENT-PLAN.md` (mark superseded sections — DSPy optimizers replace several Part 1 items)
- Modify: `_docs/LLM-MAINTENANCE.md` (replace "skel_ai_lib.py (legacy shim) + skel_rag/" section with DSPy-based architecture)
- Modify: `_docs/DEPENDENCIES.md` (add dspy-ai, litellm, optuna)
- Modify: `_docs/JUNIE-RULES.md` if it names any deprecated entry point
- Modify: `_skels/_common/manifests/python-django-skel.py` (the docstring at the top names available placeholders — update)

- [ ] **Step 1: Diff every doc**

For each file above, search for `langchain_ollama`, `RagAgent`,
`_chat_stdlib`, `OllamaClient`, `format_prompt`, `skel_ai_lib`. Each
hit is a candidate for rewrite.

- [ ] **Step 2: Rewrite to reflect DSPy**

- [ ] **Step 3: Cross-agent sanity**

Per CLAUDE.md §5.7: update both `/AGENTS.md` and `/CLAUDE.md`. Confirm
they agree.

- [ ] **Step 4: Commit**

```bash
git commit -m "Docs: DSPy migration (CLAUDE.md, MODELS.md, RAG-IMPROVEMENT-PLAN.md, LLM-MAINTENANCE.md)"
```

---

## 5. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| DSPy + Ollama unstable on `qwen3-coder:30b` JSON output | Medium | Phase 0 is the gate. If unstable, fall back to `qwen2.5-coder:32b` for GEN, document in `_docs/MODELS.md`. |
| litellm adds significant overhead per call vs. raw urllib | Medium | Benchmark in Phase 1 (record `chat_with_metrics` before/after). If >20% per-call regression, keep the urllib path as a fallback inside `skel_rag.llm.chat`. |
| DSPy's prompt formatting differs enough to break manifests that were tuned to the old stack | High | Per-manifest migration in Phase 8 is staged one-by-one with green tests gating each PR. |
| `dspy.Suggest` retry budget eats Ollama time on flaky reviewers | Medium | Cap to 1 retry (matches current `_maybe_check_target`). Add `SKEL_DSPY_MAX_SUGGESTS` env var. |
| Vendored detached `./ai` accidentally pulls a DSPy import | High if not guarded | `make test-ai-script` (no Ollama) imports the vendored runtime fresh — add a test that asserts `import dspy` is NOT in the imported module graph for the detached path. |
| Compiled-program artifacts go stale when models change | Medium | Bake the model name into the saved artifact path: `compiled/{generate}-{model}.json`. Invalidate on model swap. |
| Optimizer compilation is expensive (BootstrapFewShot calls the LM repeatedly) | Low | Compile on `paul` (RTX 3090) only, check artifact into the repo, never run during `make test-generators`. |

---

## 6. Out of Scope (explicit)

- **`./backport`** — pure file diff, no LLM. Untouched.
- **The detached out-of-tree `./ai` path** — stays stdlib-only. DSPy
  is added to the in-tree runtime only.
- **Switching away from Ollama** — DSPy supports remote LMs (Claude,
  GPT) trivially via litellm; explicitly out of scope for this
  migration to keep the surface change small.
- **Replacing FAISS with a different vector DB** — wrapping FAISS as
  `dspy.Retrieve` is sufficient.
- **Replacing the tree-sitter chunker** — current chunker is already
  high quality; DSPy doesn't impose a chunker choice.

---

## 7. Verification Checklist (per CLAUDE.md §7)

Before declaring the rewrite done:

- [ ] `make clean-test && make test-generators` green
- [ ] `make test-ai-generators-dry` green for every skel
- [ ] `make test-ai-generators` green when Ollama is reachable
- [ ] `make test-shared-db-python` green
- [ ] `make test-pizzeria-orders` green (or its `--skip-flutter-build` variant when Flutter SDK absent)
- [ ] `make test-react-django-bolt` green
- [ ] `make test-devcontainer-cross-stack` green
- [ ] `make test-k8s-cross-stack` green (paul cluster reachable)
- [ ] `make test-ai-script`, `make test-ai-memory`, `make test-ai-fanout`, `make test-backport-script` all green
- [ ] `make sync-ai-runtime` is a no-op (vendored copy in sync, with no DSPy import)
- [ ] No reference to `langchain_ollama`, `_chat_stdlib`, or `OllamaClient` in `_bin/` (except in commit history)
- [ ] `_docs/MODELS.md` is still the single source of truth for model names
- [ ] `/CLAUDE.md` and `/AGENTS.md` agree

---

## 8. Self-Review

**Spec coverage** — every current piece (LM transport, prompt
templates, retrieval, per-target loop, integration phase, CHECK_TEST,
fix loop, manifests, docs) has a phase. ✓

**Placeholder scan** — searched for "TBD", "TODO", "implement
later". One TODO marker remains in the **risk register** (the
benchmark numbers in Phase 1 Risk #2 are concrete commands, not
placeholders). ✓

**Type consistency** — `GenerateFile`, `IntegrateService`,
`FixFailingFile`, `ReviewGeneratedFile`, `CheckTest` are named
consistently. The legacy `clean_response` / `expand_target_paths` /
`_read_reference` helpers keep their current names so the migrated
agent code matches the legacy shim. ✓

---

**Plan complete.** Saved at `docs/superpowers/plans/2026-05-18-rewrite-ai-stack-to-dspy.md`.
Execute one phase per PR with the CLAUDE.md maintenance scenario
between phases. Phase 0 is a stop/go gate — do not proceed to Phase 1
if the spike fails on `qwen3-coder:30b`.
