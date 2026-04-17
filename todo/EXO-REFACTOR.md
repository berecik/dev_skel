# Exo LLM Provider Integration Plan

This document is the implementation-ready plan for adding **Exo** as an
optional LLM provider alongside Ollama. Every change is grounded in concrete
file paths and line numbers from the current tree (audited 2026-04-16) so a
follow-up agent can apply the diff without re-discovering the surface area.

The plan is split into:

1. Background & guiding principles
2. Surface area to touch (every file that mentions Ollama today)
3. Detailed code changes (per file)
4. Test plan — unit, integration, end-to-end + a dedicated **fix-loop** test
5. Manual fix-loop verification protocol (the one to run after every change)
6. Documentation updates
7. Migration / rollout sequence

---

## 1. Background & Guiding Principles

**What is Exo?** A distributed LLM runtime that splits inference across a
local cluster of devices. It exposes an **OpenAI-compatible** chat API
(default `http://localhost:52415/v1/chat/completions`) and a
`GET /v1/models` discovery endpoint. Because Exo speaks the OpenAI dialect,
the integration boils down to:

- pointing a generic OpenAI-compatible client at Exo's `base_url`,
- swapping Ollama's `/api/tags` health check for Exo's `/v1/models`,
- keeping every existing call site (`OllamaClient`, `OllamaConfig`,
  `OllamaError`) **import-compatible** so the legacy shim does not break.

**Guiding principles (do not violate):**

- **No breaking changes for current Ollama users.** `OllamaConfig`,
  `OllamaClient`, and `OllamaError` remain importable under their existing
  names. Only their internals branch on the active provider.
- **Stdlib-only fallback path stays alive.** `_bin/skel_rag/llm.py` must
  still work when `langchain-*` is not installed (see the `_HAS_LANGCHAIN`
  guard at `_bin/skel_rag/llm.py:79`). The Exo branch must offer the same
  guarantee.
- **Lazy heavy imports.** `langchain-openai` (the cleanest LangChain entry
  point for OpenAI-compatible providers) is imported lazily, exactly the way
  `langchain_ollama` is today (`_bin/skel_rag/llm.py:81`).
- **One source of truth for env vars.** Add `SKEL_LLM_PROVIDER` (`ollama` |
  `exo`) and a small set of `EXO_*` variables. Never silently flip the
  default — Ollama remains the default until the docs and CI gates are
  ready.
- **Provider-aware verify().** `verify()` MUST surface a single actionable
  error per provider so the test-and-fix loop and `OllamaClient.verify()`
  shim keep working unchanged.

---

## 2. Surface Area To Touch

Audited grep of every Ollama-aware file in the repo:

| File | What it owns today | Must change for Exo |
| ---- | ------------------ | ------------------- |
| `_bin/skel_rag/config.py` | `OllamaConfig` dataclass + env loader (`config.py:40-79`). | Add `LlmProvider` enum + `LlmConfig` (Ollama remains a thin alias). New `EXO_*` env vars + `EXO_DEFAULT_*` constants. |
| `_bin/skel_rag/llm.py` | `verify()`, `_chat_stdlib()`, `make_chat_model()`, `chat()` — all hardcoded to Ollama's REST API and `ChatOllama` (`llm.py:44-201`). | Provider branch in every public function. Add `_chat_stdlib_openai()` for Exo and `_make_chat_model_openai()` (lazy `from langchain_openai import ChatOpenAI`). |
| `_bin/skel_rag/agent.py` | `RagAgent.__init__` takes `OllamaConfig` (`agent.py:54-63`); `chat()` calls `llm_chat(self.ollama_cfg, …)` (`agent.py:67-70`). | Accept `LlmConfig` (alias of `OllamaConfig`). No call-site change beyond the rename — `llm_chat` becomes provider-aware internally. |
| `_bin/skel_rag/__init__.py` | Re-exports `OllamaConfig` (`__init__.py:73-78`). | Also re-export `LlmConfig`, `LlmProvider`. |
| `_bin/skel_ai_lib.py` | Legacy `OllamaConfig` (`skel_ai_lib.py:62-98`), `OllamaError` (`skel_ai_lib.py:543`), `OllamaClient` (`skel_ai_lib.py:547-611`). | `OllamaConfig.from_env()` learns about `SKEL_LLM_PROVIDER`. `OllamaClient.verify` / `chat` keep delegating — they get Exo for free. Update `__all__` (`skel_ai_lib.py:2298`) to also export `LlmConfig` / `LlmProvider`. |
| `_bin/skel-gen-ai` | CLI flags `--ollama-model` / `--ollama-url` / `--ollama-temperature` (`skel-gen-ai:273-279`); `_build_ollama_config` (`skel-gen-ai:355-364`). | Add `--llm-provider`, `--exo-model`, `--exo-url`, `--exo-temperature`. Either flag set may override env. Provider also overridable via `SKEL_LLM_PROVIDER`. |
| `_bin/skel-test-ai-generators` | Imports `OllamaClient`, `OllamaConfig`, `OllamaError` (`skel-test-ai-generators:55-65`). | No code changes required — it inherits Exo support via the shim. Add a `--llm-provider` passthrough flag for symmetry. |
| `_bin/skel_rag/tests/test_phases.py` | Hardcodes `OLLAMA_BASE_URL` reachability gate (`test_phases.py:66-80`). | New equivalent gate that checks the active provider. Same for `_bin/skel_rag/tests/test_phase4_e2e.py:59-74`. |
| `_bin/skel-install-rag` | Pip-installs `langchain-ollama` (`skel-install-rag:67-74`). | Also install `langchain-openai>=0.2`. Keep the verify block (`skel-install-rag:86-93`) — extend it to import `ChatOpenAI`. |
| `Makefile` | `install-rag-deps`, `test-ai-generators*`, `rag-index-skels` (`Makefile:197-288`). | Add `test-ai-generators-exo`, `test-gen-ai-exo-<skel>`, plus an `EXO_*` block in the help text. |
| `_docs/LLM-MAINTENANCE.md` | Ollama setup, env vars, config reference (lines `87-940`). | New "Exo provider" section + a side-by-side env var table. |
| `CLAUDE.md` & `AGENTS.md` | Section 6 (`CLAUDE.md:323-356`) — "Working with the Ollama AI Generator". | Add an "Exo provider" subsection mirroring section 6. |

---

## 3. Detailed Code Changes

### 3.1 `_bin/skel_rag/config.py`

Add at the top of the module (after the existing `DEFAULT_OLLAMA_*`
constants at `config.py:29-37`):

```python
from enum import Enum

# Exo runs an OpenAI-compatible chat server. The default port is the upstream
# default; override with EXO_BASE_URL when the cluster head is on a remote
# host. The model name is whatever Exo registered ("llama-3.2-3b" etc.) —
# leave it required so misconfiguration fails fast.
DEFAULT_EXO_BASE_URL = "http://localhost:52415"
DEFAULT_EXO_MODEL = "llama-3.2-3b"


class LlmProvider(str, Enum):
    OLLAMA = "ollama"
    EXO = "exo"

    @classmethod
    def from_env(cls, default: "LlmProvider" = None) -> "LlmProvider":
        raw = os.environ.get("SKEL_LLM_PROVIDER", "").strip().lower()
        if not raw:
            return default or cls.OLLAMA
        try:
            return cls(raw)
        except ValueError as exc:
            raise ValueError(
                f"SKEL_LLM_PROVIDER={raw!r} is not one of "
                f"{', '.join(p.value for p in cls)}"
            ) from exc
```

Refactor `OllamaConfig` (`config.py:40-79`) into a generic `LlmConfig` and
keep `OllamaConfig` as a backward-compatible alias:

```python
@dataclass
class LlmConfig:
    """Connection details for an OpenAI-compatible chat backend."""

    provider: LlmProvider = LlmProvider.OLLAMA
    model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    temperature: float = DEFAULT_TEMPERATURE
    api_key: Optional[str] = None  # Exo accepts any non-empty bearer; Ollama ignores

    @classmethod
    def from_env(cls) -> "LlmConfig":
        provider = LlmProvider.from_env()
        if provider is LlmProvider.EXO:
            return cls._from_env_exo()
        return cls._from_env_ollama()

    @classmethod
    def _from_env_ollama(cls) -> "LlmConfig":
        # Body is the existing OllamaConfig.from_env logic at config.py:50-79
        # — moved verbatim, only difference is `provider=LlmProvider.OLLAMA`.
        ...

    @classmethod
    def _from_env_exo(cls) -> "LlmConfig":
        base = os.environ.get("EXO_BASE_URL", DEFAULT_EXO_BASE_URL).rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        return cls(
            provider=LlmProvider.EXO,
            model=os.environ.get("EXO_MODEL", DEFAULT_EXO_MODEL),
            base_url=base,
            timeout=_int_env("EXO_TIMEOUT", DEFAULT_TIMEOUT),
            temperature=_float_env("EXO_TEMPERATURE", DEFAULT_TEMPERATURE),
            api_key=os.environ.get("EXO_API_KEY") or None,
        )


# Backward-compat alias — old code does `from skel_rag.config import OllamaConfig`.
# We keep the class importable; `from_env()` still defaults to Ollama if
# SKEL_LLM_PROVIDER is unset, so existing callers see no behaviour change.
OllamaConfig = LlmConfig
```

`_int_env` / `_float_env` are tiny helpers extracted from the existing
inline `try/except` blocks at `config.py:64-73`.

### 3.2 `_bin/skel_rag/llm.py`

**verify()** — branch on provider (`llm.py:44-72`):

```python
def verify(config: LlmConfig) -> None:
    if config.provider is LlmProvider.EXO:
        return _verify_exo(config)
    return _verify_ollama(config)


def _verify_ollama(config: LlmConfig) -> None:
    # Existing body of verify() — the GET /api/tags check at llm.py:55-72.
    ...


def _verify_exo(config: LlmConfig) -> None:
    """Exo speaks OpenAI: GET /v1/models returns {'data': [{'id': '...'}]}."""

    url = f"{config.base_url}/v1/models"
    request = urllib.request.Request(url)
    if config.api_key:
        request.add_header("Authorization", f"Bearer {config.api_key}")
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaError(  # KEEP the OllamaError name — see "Naming" below
            f"Could not reach Exo at {config.base_url}: {exc}.\n"
            "Make sure `exo` is running, or set EXO_BASE_URL."
        ) from exc

    ids = [m.get("id", "") for m in payload.get("data", [])]
    if config.model not in ids:
        available = ", ".join(sorted(i for i in ids if i)) or "(none)"
        raise OllamaError(
            f"Exo model '{config.model}' is not available.\n"
            f"Models present: {available}\n"
            f"Pull/load it via the Exo UI or set EXO_MODEL=<one of the above>."
        )
```

**Naming note:** `OllamaError` keeps its name (it's part of the public
import surface — `_bin/skel_ai_lib.py:543`, re-imported in `skel-gen-ai`,
`skel-test-ai-generators`, and both phase test files). Leaving the name
alone avoids touching ~20 call sites for a cosmetic rename. Add a docstring
clarifying it now means "any LLM provider error".

**_chat_stdlib() → _chat_stdlib_openai()**:

Both Ollama and Exo expose `/v1/chat/completions` — the existing stdlib
implementation at `llm.py:93-128` already targets that endpoint. Promote it
to a provider-aware function that adds the `Authorization` header when
`config.api_key` is set:

```python
def _chat_stdlib(config: LlmConfig, system: str, user: str) -> str:
    url = f"{config.base_url}/v1/chat/completions"
    body = { ... }  # unchanged from llm.py:97-105
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers,
    )
    # Error wrapping unchanged at llm.py:110-128 — friendly message
    # already references "Ollama"; switch to a provider-aware string:
    provider_name = "Exo" if config.provider is LlmProvider.EXO else "Ollama"
```

**make_chat_model()** — branch on provider (`llm.py:136-157`):

```python
@lru_cache(maxsize=4)
def _make_chat_model(provider: str, model: str, base_url: str,
                     temperature: float, timeout: int,
                     api_key: Optional[str]) -> Any:
    if provider == LlmProvider.EXO.value:
        return _make_chat_model_openai(model, base_url, temperature, timeout, api_key)
    return _make_chat_model_ollama(model, base_url, temperature, timeout)


def _make_chat_model_ollama(...):  # existing body of llm.py:140-146
    ...


def _make_chat_model_openai(model, base_url, temperature, timeout, api_key):
    # langchain-openai is imported lazily so machines without the dep
    # still get the stdlib fallback (mirrors _HAS_LANGCHAIN at llm.py:79).
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
    except ImportError:
        return None
    return ChatOpenAI(
        model=model,
        base_url=f"{base_url}/v1",
        temperature=temperature,
        timeout=float(timeout),
        # Exo accepts any non-empty bearer; default sentinel keeps the
        # client happy when EXO_API_KEY is unset.
        api_key=api_key or "exo-local",
    )
```

`make_chat_model(config)` then forwards `config.provider.value`,
`config.api_key`, and the rest. Update the cache key so a provider swap
within a single Python process does not return a stale model.

**chat()** — at `llm.py:160-201`, the only edit is the Exception fallback
message: `"Ollama request failed"` → `f"{provider_name} request failed"`.

### 3.3 `_bin/skel_rag/agent.py`

Two-line rename + alias:

- `agent.py:29` — change import to `from skel_rag.config import LlmConfig as OllamaConfig, RagConfig`. Keep the local name `OllamaConfig` so the rest of the file is unchanged.
- `agent.py:54-63` — `__init__` signature gets a `llm_cfg: Optional[LlmConfig] = None` keyword (alias of `ollama_cfg` for back-compat); store as `self.llm_cfg` (or keep `self.ollama_cfg` — pick one, document it).

No other change. `llm_chat(self.ollama_cfg, …)` already accepts the generic
config because `OllamaConfig` IS `LlmConfig`.

### 3.4 `_bin/skel_rag/__init__.py`

Append to the import at `__init__.py:73`:

```python
from skel_rag.config import LlmConfig, LlmProvider, OllamaConfig, RagConfig

__all__ = ["LlmConfig", "LlmProvider", "OllamaConfig", "RagConfig"]
```

### 3.5 `_bin/skel_ai_lib.py`

- `skel_ai_lib.py:62-98` — replace the local `OllamaConfig` class with
  `from skel_rag.config import LlmConfig as OllamaConfig, LlmProvider`.
  Drop the duplicated env-loading code; the canonical loader now lives in
  `skel_rag.config`.
- `skel_ai_lib.py:2298` (`__all__`) — add `"LlmConfig"`, `"LlmProvider"`.
- `OllamaClient` (`skel_ai_lib.py:547-611`) is unchanged: it already
  delegates to `RagAgent` and `skel_rag.llm`, both of which become
  provider-aware after 3.1–3.3.

### 3.6 `_bin/skel-gen-ai`

After `--ollama-temperature` at `skel-gen-ai:279`, add:

```python
parser.add_argument(
    "--llm-provider",
    choices=["ollama", "exo"],
    help="LLM backend (default: $SKEL_LLM_PROVIDER, then ollama)",
)
parser.add_argument("--exo-model", help="Override EXO_MODEL for this run")
parser.add_argument("--exo-url", help="Override EXO_BASE_URL for this run")
parser.add_argument("--exo-temperature", type=float, help="EXO sampling temperature")
parser.add_argument(
    "--exo-api-key",
    help="Override EXO_API_KEY (Exo accepts any non-empty bearer; default 'exo-local')",
)
```

Refactor `_build_ollama_config` (`skel-gen-ai:355-364`) into
`_build_llm_config(args)` that:

1. Picks the provider: `args.llm_provider` > `SKEL_LLM_PROVIDER` > Ollama.
2. Sets the matching env vars in `os.environ` *before* calling
   `LlmConfig.from_env()` so the loader sees them. (Or builds the config
   manually — pick whichever is shorter; the env-mutation route keeps the
   loader the single source of truth.)
3. Applies CLI overrides on top of the loaded config.

Keep the function name `_build_ollama_config` exported (or alias it) so
in-tree imports do not break, but rename internally.

### 3.7 `_bin/skel-test-ai-generators`

No required changes — `OllamaClient` does the right thing now. Optional
nicety: surface `--llm-provider` as a passthrough so CI can run the same
matrix against Exo:

```python
parser.add_argument("--llm-provider", choices=["ollama", "exo"])
# ...
if args.llm_provider:
    os.environ["SKEL_LLM_PROVIDER"] = args.llm_provider
```

### 3.8 `_bin/skel-install-rag`

Edit `skel-install-rag:66-74`:

```bash
"$PIP" install --upgrade \
    'langchain-core>=0.3' \
    'langchain-community>=0.3' \
    'langchain-huggingface>=0.1' \
    'langchain-ollama>=0.2' \
    'langchain-openai>=0.2' \      # NEW
    'langchain-text-splitters>=0.3' \
    ...
```

And the verify block at `skel-install-rag:86-93`:

```python
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI    # NEW
```

### 3.9 `Makefile`

Add after the existing AI block (`Makefile:197-233`):

```makefile
# === EXO LLM PROVIDER ===
#
# Exo is an OpenAI-compatible distributed LLM. Activate with
# SKEL_LLM_PROVIDER=exo (and optionally EXO_BASE_URL / EXO_MODEL).
# These targets force the env so the runner picks Exo regardless of shell
# configuration.

EXO_ENV := SKEL_LLM_PROVIDER=exo

test-ai-generators-exo: ## Same as test-ai-generators but pin provider=exo
	@echo "$(GREEN)=== Running AI generators against EXO ===$(NC)"
	@$(EXO_ENV) _bin/skel-test-ai-generators --llm-provider exo

test-gen-ai-exo-django-bolt: ## AI-generate via Exo for django-bolt only
	@$(EXO_ENV) _bin/skel-test-ai-generators --llm-provider exo --skel python-django-bolt-skel

test-gen-ai-exo-fastapi:
	@$(EXO_ENV) _bin/skel-test-ai-generators --llm-provider exo --skel python-fastapi-skel
# (...one target per AI-supported skeleton, mirroring test-gen-ai-<skel>)
```

Add the new targets to the `.PHONY` list at `Makefile:4-17`.

### 3.10 `_docs/LLM-MAINTENANCE.md`

Two edits:

- New "Exo provider" subsection right after the Ollama setup block
  (around `LLM-MAINTENANCE.md:920-940`). Side-by-side env var table:

  | Variable | Ollama | Exo |
  | -------- | ------ | --- |
  | Provider switch | (default) | `SKEL_LLM_PROVIDER=exo` |
  | Base URL | `OLLAMA_BASE_URL` (default `http://localhost:11434`) | `EXO_BASE_URL` (default `http://localhost:52415`) |
  | Model | `OLLAMA_MODEL` (default `gemma4:31b`) | `EXO_MODEL` (no sensible global default — set explicitly) |
  | Timeout | `OLLAMA_TIMEOUT` | `EXO_TIMEOUT` |
  | Temperature | `OLLAMA_TEMPERATURE` | `EXO_TEMPERATURE` |
  | Auth | n/a | `EXO_API_KEY` (any non-empty string) |

- Update the `_bin/skel_rag/llm.py` description (`LLM-MAINTENANCE.md:856`)
  to mention provider branching.

### 3.11 `CLAUDE.md` / `AGENTS.md`

Section 6 of `CLAUDE.md` (`CLAUDE.md:323-356`) gets a new step:

> 0. Decide the provider. If `SKEL_LLM_PROVIDER=exo` is set, verify
>    Exo is running (`curl -sf http://localhost:52415/v1/models`) instead
>    of Ollama. The `EXO_*` env vars override the `OLLAMA_*` ones; do NOT
>    set both.

Mirror the same insertion in `/AGENTS.md`.

---

## 4. Test Plan

### 4.1 Unit tests (no Ollama / Exo required)

Add `_bin/skel_rag/tests/test_llm_provider.py`:

- `test_llm_provider_default_ollama_when_unset` — clear `SKEL_LLM_PROVIDER`, expect `LlmConfig.from_env().provider is LlmProvider.OLLAMA`.
- `test_llm_provider_exo_via_env` — set `SKEL_LLM_PROVIDER=exo`, `EXO_BASE_URL`, `EXO_MODEL`; expect the loader returns the right values + normalises a trailing `/v1`.
- `test_llm_provider_invalid_value_raises` — `SKEL_LLM_PROVIDER=foo` → `ValueError`.
- `test_ollama_config_alias_imports` — `from skel_rag.config import OllamaConfig` still works and is `is LlmConfig`.
- `test_make_chat_model_branches_on_provider` — monkeypatch the lazy imports to assert that `provider=ollama` calls `ChatOllama` and `provider=exo` calls `ChatOpenAI` (the latter wrapped with `base_url=…/v1` and a default `api_key`).
- `test_verify_exo_uses_v1_models` — patch `urllib.request.urlopen` and assert `verify(LlmConfig(provider=EXO, ...))` issues a GET to `/v1/models`.
- `test_chat_stdlib_sends_bearer_when_api_key_set` — assert the `Authorization: Bearer …` header is present in the stdlib path for Exo, absent for Ollama.

These are pure stdlib tests; they belong in the existing pytest layout
under `_bin/skel_rag/tests/`. They MUST run as part of `make
test-generators` (i.e. the cheap CI tier) — wire them in by adding a small
`pytest` invocation to `Makefile:107-121` if no equivalent exists yet, or
keep them in their current implicit `pytest _bin/skel_rag/tests/` discovery.

### 4.2 Integration tests against a live Exo

Mirror the existing Ollama integration tests:

- `_bin/skel_rag/tests/test_phases_exo.py` — clone of `test_phases.py`
  with the reachability gate at `test_phases.py:66-75` rewritten to probe
  `EXO_BASE_URL/v1/models` and `pytestmark` swapped accordingly. Mark
  with `pytest.mark.exo`.
- `_bin/skel_rag/tests/test_phase4_e2e_exo.py` — same treatment for the
  Phase-4 end-to-end test (`test_phase4_e2e.py`).

These tests SHOULD use the same `python-django-bolt-skel` target as the
Ollama tests so a side-by-side run produces directly comparable artefacts.

### 4.3 Provider parity test

Add `_bin/skel_rag/tests/test_provider_parity.py`:

- Skips when EITHER provider is unreachable.
- Generates the same single tiny target (the smallest manifest target —
  e.g. `python-fastapi-skel` `app/config.py`) under both providers.
- Asserts both runs produce a non-empty file with the same item class
  string. Output bytes will differ — assert structural properties only
  (no `import` errors, file syntactically valid via `py_compile`).

This is the regression net that catches "Exo subtly broke the prompt
shape" failures.

### 4.4 Cross-stack & shared-DB tests (no change)

`make test-react-django-bolt`, `make test-shared-db`, etc. are agnostic to
the provider — they call `skel-gen` (static) and exercise generated code,
not Ollama. They run unchanged but become powerful Exo-vs-Ollama
A/B comparisons when prefixed with `SKEL_LLM_PROVIDER=exo`.

### 4.5 Dedicated fix-loop integration test

Add `_bin/skel_rag/tests/test_fix_loop_provider.py`:

- Generate a deliberately-broken integration target (use a tiny manifest
  fixture under `_bin/skel_rag/tests/fixtures/` that emits a Python file
  with a `SyntaxError`).
- Run `run_test_and_fix_loop` with a 3-iteration cap and a 3-minute
  per-iteration timeout.
- Assert:
  1. The loop ran at least once (`final.iterations >= 1`).
  2. After repair, the file is syntactically valid (`py_compile`).
  3. The provider used was the one in `SKEL_LLM_PROVIDER`.
- Parametrise over `["ollama", "exo"]`, skipping each branch when its
  backend is unreachable.

This test is the **automated** equivalent of the manual fix-loop checklist
in §5; both are required because the manual run catches things like
"the user's actual Exo cluster has different model availability" while the
automated test guards regressions in the orchestration code.

---

## 5. Manual Fix-Loop Verification Protocol

Run this checklist after **every** code change in §3. The goal is to prove
the new provider works end-to-end through the same fix-loop machinery the
existing Ollama path relies on. Treat each green check as a hard blocker
for landing the change.

### Preflight

- [ ] Exo running: `curl -sf http://localhost:52415/v1/models | jq .data`.
- [ ] `EXO_MODEL` exported and present in the curl output above.
- [ ] `make install-rag-deps` ran clean (the new `langchain-openai` line in
      `_bin/skel-install-rag` succeeded).
- [ ] `python3 -c "from skel_rag.config import LlmProvider, LlmConfig; print(LlmConfig.from_env())"` prints an `LlmConfig` whose `provider` matches `$SKEL_LLM_PROVIDER`.

### Cheap dispatch tests (under 30 s)

- [ ] `make test-ai-generators-dry` (verifies wrapper scaffold + manifest
      load with no Ollama/Exo call). Must remain green after the refactor.
- [ ] `pytest _bin/skel_rag/tests/test_llm_provider.py -v` — all unit
      tests above pass.

### Single-target Ollama smoke test (regression guard)

- [ ] Unset `SKEL_LLM_PROVIDER`, run
      `_bin/skel-test-ai-generators --skel python-django-bolt-skel`. Confirm
      it still reaches Ollama and writes the per-target files (~5 min).
- [ ] Confirm the printed banner reads `Ollama: <model> @ http://localhost:11434`.

### Single-target Exo smoke test

- [ ] `SKEL_LLM_PROVIDER=exo EXO_MODEL=<your-model> _bin/skel-test-ai-generators --llm-provider exo --skel python-django-bolt-skel`.
- [ ] Confirm the printed banner reads `Exo: <model> @ http://localhost:52415`.
- [ ] Compare the generated `app/api.py` against the Ollama-generated one.
      Differences are expected; what matters is that both files import
      cleanly (`python -m py_compile`) and that the AI did not switch
      languages or drop the `{item_class}` interpolation.

### Full integration + fix loop (Exo)

- [ ] `SKEL_LLM_PROVIDER=exo EXO_MODEL=<your-model> pytest _bin/skel_rag/tests/test_phase4_e2e_exo.py -v -s`.
- [ ] Watch the `Test-and-fix loop:` lines in stdout. The loop MUST
      exercise at least one repair cycle (the deliberate-break fixture in
      §4.5 forces this). If it never iterates, the loop is short-circuiting
      — diagnose `RagAgent.fix_target` and the `OllamaError` re-raise path
      in `OllamaClient.chat`.
- [ ] At the end, assert `final.passed is True` (the loop drove the
      generated tests green).

### Provider-parity sanity

- [ ] `pytest _bin/skel_rag/tests/test_provider_parity.py -v` with both
      backends running.
- [ ] On failure, dump both generated files, diff them, and add the
      missing prompt safeguard before re-running.

### Documentation diff sanity

- [ ] `_docs/LLM-MAINTENANCE.md` mentions Exo wherever it mentions Ollama.
- [ ] `CLAUDE.md` § 6 has the new "Decide the provider" step.
- [ ] `AGENTS.md` mirrors the Claude file.

### Roll-back rehearsal

- [ ] `unset SKEL_LLM_PROVIDER && make test-ai-generators-dry` is still
      green — proves the default path is unchanged.
- [ ] `git stash` the Exo changes, re-run `make test-ai-generators-dry`,
      `git stash pop`. Behaviour identical → safe to ship.

If any checkbox above fails, **do not merge**. File an inline TODO with
the failure mode and re-run the loop after the fix.

---

## 6. Documentation Updates

Mandatory edits — none of these are optional:

1. `_docs/LLM-MAINTENANCE.md` — new "Exo provider" subsection (see §3.10).
2. `_docs/JUNIE-RULES.md` — add a one-liner under the "AI generator" rule
   noting that the provider can now be switched via `SKEL_LLM_PROVIDER`.
3. `CLAUDE.md` § 6 — see §3.11.
4. `/AGENTS.md` — mirror of `CLAUDE.md` § 6.
5. README.md / project-level docs — only if they currently mention Ollama
   by name (audit with `grep -rin ollama _docs/ README.md`).

Optional but recommended:

- A short cookbook entry under `_docs/` showing the env vars to set when
  bringing up an Exo cluster on a laptop + Mac mini cluster.

---

## 7. Migration / Rollout Sequence

Apply the changes in this order so each step is independently testable:

1. **Plumbing only** — §3.1 (`LlmConfig` + `LlmProvider`) + §3.4
   (re-exports) + §3.5 (alias in `skel_ai_lib`). Run §4.1 unit tests.
2. **Provider-aware llm.py** — §3.2. Run §4.1 again; the cached
   `make_chat_model` cache key change is the most error-prone bit.
3. **Agent + CLI flags** — §3.3 + §3.6 + §3.7. Run §4.4 cross-stack tests
   to confirm nothing regressed for the static path.
4. **Installer + Makefile** — §3.8 + §3.9. Run `make install-rag-deps` end
   to end and confirm the new `ChatOpenAI` import succeeds.
5. **Live tests** — §4.2, §4.3, §4.5. Iterate against a real Exo node.
6. **Docs** — §3.10 + §3.11 + §6.
7. **Roll-back rehearsal** — last bullet of §5.

Once the manual fix-loop checklist (§5) is fully green for **both**
providers, land the change as a single commit with the §3 file list in
the body and a `Co-Authored-By` trailer.
