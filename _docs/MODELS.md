# Ollama Models — Single Source of Truth

All model defaults live in **one file**:
[`_bin/skel_rag/config.py`](../_bin/skel_rag/config.py) — the
`DEFAULT_OLLAMA_*_MODEL` constants and the `OllamaConfig` dataclass.

## DSPy LM factory

Since the DSPy migration (Phase 8a, 2026-05-19) the canonical
chat-LM constructor is **`skel_rag.dspy_lm.make_lm(cfg)`**. It
returns a `dspy.LM("ollama_chat/<model>")` instance backed by
[litellm](https://github.com/BerriAI/litellm) — DSPy's HTTP
transport — wired to the same `OllamaConfig` resolution rules the
rest of the codebase uses. `langchain_ollama` is no longer
imported anywhere under `_bin/`.

The per-phase variants on `OllamaConfig` (`for_fix`,
`for_create_test`, `for_check_test`, `for_docs`, legacy `for_test`)
still work — `make_lm` is invoked per-config, so each phase gets a
DSPy LM bound to the right model, temperature, and timeout. The
phase-swap semantics are unchanged; only the transport layer
moved.

```python
from skel_rag.config import OllamaConfig
from skel_rag.dspy_lm import make_lm

cfg = OllamaConfig.from_env()
gen_lm  = make_lm(cfg)                 # GEN phase
fix_lm  = make_lm(cfg.for_fix())       # FIX phase (lower temp, shorter timeout)
docs_lm = make_lm(cfg.for_docs())      # DOCS phase
```

The full DSPy pipeline (`signatures/`, `programs/`,
`dspy_retriever.py`, `optimize.py`, `trainset.py`) is documented
in `_docs/LLM-MAINTENANCE.md`. Until the default flip lands, the
DSPy code path is opt-in via **`SKEL_RAG_USE_DSPY=1`**.

Every consumer (`skel-gen-ai`, `./ai`, `./backport`, `skel_ai_lib`,
the refactor runtime) reads its model from this module — either by
importing the constant directly, or by calling
`OllamaConfig.from_env().for_<phase>()`.

`_bin/skel_ai_lib.py` previously carried a duplicate `OllamaConfig`
stub without the per-phase methods; that stub is removed and the
module now re-exports `OllamaConfig` from `skel_rag.config` so old
import paths (`from skel_ai_lib import OllamaConfig`) keep working
without behavioural drift.

Override any slot via the matching environment variable; **do not**
hardcode model names elsewhere.

> **Out-of-tree exception.** `_bin/dev_skel_refactor_runtime.py` is
> vendored into detached service trees that cannot import the
> dev_skel package, so it carries a duplicated string literal that
> must be kept in sync manually. The comment at the call site flags
> this.

## Phases

The pipeline now uses **five** distinct model slots — picked so the
strengths of each model match the work it does, and so the
implementation, tests, and verification never come from the same
weights.

| Phase | Default | Override env var | Why this model |
|---|---|---|---|
| **GEN** (primary code) | `qwen3-coder:30b` | `OLLAMA_GEN_MODEL` (legacy: `OLLAMA_MODEL`) | Strong code synthesis + the highest tok/s on the target GPU. ~10× faster than `qwen3.6:27b` on the `paul` RTX 3090. |
| **CREATE_TEST** (test scaffolding) | `devstral:latest` (23.6B, Q4_K_M ≈ 14 GB on disk) | `OLLAMA_CREATE_TEST_MODEL` (legacy: `OLLAMA_TEST_MODEL`) | Mistral's code+tests specialist. **Must differ from GEN** so the test author isn't biased by the same model that wrote the implementation. |
| **CHECK_TEST** (test review/validation) | `qwq:32b` | `OLLAMA_CHECK_TEST_MODEL` | Qwen's reasoning model — better than a code specialist at noticing missing edge cases and weak assertions. |
| **FIX** (surgical patches when tests fail) | `qwen2.5-coder:32b` | `OLLAMA_FIX_MODEL` | Stable, accurate edits. Lower temperature (0.1) and shorter timeout (300 s) applied automatically by `for_fix()`. |
| **DOCS** (READMEs, docstrings, comments) | `qwen2.5:7b-instruct` | `OLLAMA_DOCS_MODEL` | Smallest model that produces clear prose. Code reasoning isn't needed — frees the GPU for parallel GEN/FIX work. |

### Contract

* **CREATE_TEST must differ from BOTH `GEN` and `FIX`** — the test
  author should not be the same model that wrote (or will patch) the
  implementation. This is checked at config-load time:
  `OllamaConfig.from_env()` prints a `[skel_rag.config] WARNING: …`
  line on stderr when CREATE_TEST overlaps with GEN or FIX. The
  warning is non-fatal so power users can opt into a degraded
  configuration explicitly, but the default lineup keeps all three
  distinct.
* **GEN and FIX may overlap by design** — both are code-focused,
  sharing the model halves cold-load time.
* CHECK_TEST and DOCS have no uniqueness requirement; the defaults
  pick them for fitness (`qwq:32b` reasoning for review, smallest
  model for prose).

## Alternative configurations

Available models on the `paul` host (RTX 3090, 24 GB VRAM):

| Model | Family | Params | Disk | Best for |
|---|---|---|---|---|
| `qwen3-coder:30b` | qwen3moe | 30.5B | 18.6 GB | GEN — fast, strong code |
| `qwen2.5-coder:32b` | qwen2 | 32.8B | 19.9 GB | FIX — stable, accurate |
| `devstral:latest` | llama | 23.6B | 14.3 GB | CREATE_TEST — Mistral test specialist; family-distinct from every other slot |
| `qwq:32b` | qwen2 | 32.8B | 19.9 GB | CHECK_TEST — reasoning |
| `qwen2.5:7b-instruct` | qwen2 | 7.6B | 4.7 GB | DOCS — small + prose |
| `gemma4:31b` | gemma4 | 31.3B | 19.9 GB | alt GEN — different family |
| `qwen3:32b` | qwen3 | 32.8B | 20.2 GB | alt GEN — generalist Qwen3 |
| `qwen3.6:27b` | qwen35 | 27.8B | 17.4 GB | (slow on RTX 3090 per benchmarks; avoid for hot paths) |
| `qwen3:14b` | qwen3 | 14.8B | 9.3 GB | alt DOCS — bigger than 7b |

Two ready-to-flip alternative configs that satisfy the uniqueness
contract:

**Cross-family GEN (Gemma + Mistral + Qwen)** — maximum diversity:
```bash
export OLLAMA_GEN_MODEL=gemma4:31b           # google
export OLLAMA_CREATE_TEST_MODEL=devstral:latest  # mistral, unique
export OLLAMA_CHECK_TEST_MODEL=qwq:32b       # qwen2 reasoning
export OLLAMA_FIX_MODEL=qwen3-coder:30b      # qwen3 coder
export OLLAMA_DOCS_MODEL=qwen2.5:7b-instruct
```

**Smaller / faster** (closer to 14B class everywhere):
```bash
export OLLAMA_GEN_MODEL=qwen3:14b
export OLLAMA_CREATE_TEST_MODEL=devstral:latest
export OLLAMA_CHECK_TEST_MODEL=qwq:32b
export OLLAMA_FIX_MODEL=qwen2.5-coder:32b
export OLLAMA_DOCS_MODEL=qwen2.5:7b-instruct
```

## Connection settings

Three env vars cover Ollama connection details:

| Variable | Default | Notes |
|---|---|---|
| `OLLAMA_BASE_URL` | (unset) | Full URL — wins if set. e.g. `https://paul:11434`. |
| `OLLAMA_HOST` | `localhost:11434` | `host:port` form, full URL, or **bare hostname** (port defaults to `11434`). `OLLAMA_HOST=paul` resolves to `http://paul:11434`. |
| `OLLAMA_TIMEOUT` | `600` | Per-request timeout in seconds. Covers cold-load + multi-minute completions. |
| `OLLAMA_TEMPERATURE` | `0.2` | Default sampling temperature. Overridden per phase by the `for_*` methods. |

> **Resolver invariant.** `_bin/skel_rag/config.py::_resolve_base_url`,
> `_bin/dev_skel_refactor_runtime.py::_resolve_base_url`, and
> `_bin/skel-test-pizzeria-orders::_ollama_base_url` all share the same
> bare-hostname → `:11434` rule. Keep them in lockstep when editing.

## Server-side performance knobs

Set these on the Ollama daemon (the server, not the client):

| Variable | Suggested | Effect |
|---|---|---|
| `OLLAMA_FLASH_ATTENTION` | `1` | 1.8–2.3× speedup on Ampere+ GPUs (RTX 3090 included). |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | ~50% less KV-cache VRAM. |
| `OLLAMA_KEEP_ALIVE` | `24h` | Keep models resident between requests so cold-load doesn't dominate. |

## Switching models per phase from code

```python
from skel_rag.config import OllamaConfig
from skel_rag.dspy_lm import make_lm

cfg = OllamaConfig.from_env()  # picks defaults + env overrides

# Implementation phase — uses cfg.model (GEN slot)
gen_lm = make_lm(cfg)

# Test scaffolding — must be a different model
tests_lm = make_lm(cfg.for_create_test())

# Validate the generated tests
review_lm = make_lm(cfg.for_check_test())

# Patch on test failure
fix_lm = make_lm(cfg.for_fix())

# Generate prose
docs_lm = make_lm(cfg.for_docs())
```

`for_*` returns a fresh `OllamaConfig` with the right model, temperature
and timeout for that phase — no other slots change, so chaining is
safe. `make_lm` returns a `dspy.LM("ollama_chat/...")` instance
backed by litellm.

## Switching models from the shell

```bash
# Smaller GPU? Override at the top level.
export OLLAMA_GEN_MODEL=qwen2.5-coder:14b
export OLLAMA_CREATE_TEST_MODEL=qwen2.5-coder:7b
export OLLAMA_CHECK_TEST_MODEL=phi4:14b
export OLLAMA_FIX_MODEL=qwen2.5-coder:14b
export OLLAMA_DOCS_MODEL=qwen2.5:3b-instruct

make test-ai-generators
```

Legacy env vars (`OLLAMA_MODEL`, `OLLAMA_TEST_MODEL`) still work and
map to GEN and CREATE_TEST respectively, so existing scripts do not
need to change.

## Verification

```bash
# Confirm the resolved per-phase models
python3 - <<'PY'
import sys; sys.path.insert(0, '_bin')
from skel_rag.config import OllamaConfig
c = OllamaConfig.from_env()
print(f'gen          = {c.model}')
print(f'create_test  = {c.create_test_model}')
print(f'check_test   = {c.check_test_model}')
print(f'fix          = {c.fix_model}')
print(f'docs         = {c.docs_model}')
assert c.model != c.create_test_model, 'CREATE_TEST must differ from GEN'
PY
```
