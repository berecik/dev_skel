# Dev Skel Documentation

This directory is the reference manual for Dev Skel — the multi-service
project generator that **ships every generated service with its own
in-service code agent**. The top-level [`README.md`](../README.md) is
the one-page overview; the files here go into depth per topic.

If you're new here, start with [`../README.md`](../README.md) →
[Generator](#1-the-generator-skel-gen-ai) →
[In-service agent](#2-the-in-service-code-agent-ai) →
[Template ↔ service sync](#3-template--service-sync-backport--ai-upgrade).

---

## The three AI surfaces (cheat sheet)

```
                   _bin/skel-gen-ai
  dev_skel  ─────────────────────────────►  <project>/
  checkout       (full-stack dialog,            │
                  5-phase Ollama run)           │
                                                │
                      ◄──────── ./backport ─────┤
                                (promote          │
                                 service→template)│
                                                  │
                      ────────► ./ai upgrade ─────┤
                                (pull template    │
                                 →service)        │
                                                  │
                                                  ▼
                                        ┌─────────────────────┐
                                        │  <service>/         │
                                        │    ./ai             │
                                        │    .ai_runtime.py   │
                                        │    .skel_context.json│
                                        │    .ai/memory.jsonl │
                                        └─────────────────────┘
```

Wrapper-level `./ai` (auto-generated at `<project>/ai`) **fans out by
default**, so a single request at the project root lands in every
service.

---

## Documentation index

### 1. The generator (`skel-gen-ai`)

* [**LLM-MAINTENANCE.md**](LLM-MAINTENANCE.md) — the complete reference
  for the AI pipeline. Manifests, the RAG agent (`_bin/skel_rag/`),
  the five-phase orchestrator, the fix-loop, the sibling discovery
  format, prompt placeholders. **Start here** when extending
  `skel-gen-ai`, adding a manifest, or debugging a generation.
* [**SKELETONS.md**](SKELETONS.md) — per-skeleton summary: what AI
  manifest each skel ships, what entity slots it exposes
  (`{item_class}`, `{items_plural}`, `{backend_extra}` …), items API
  contract status, service-directory conventions.
* Per-skeleton deep-dives — [`python-fastapi-skel.md`](python-fastapi-skel.md),
  [`python-django-bolt-skel.md`](python-django-bolt-skel.md),
  [`ts-react-skel.md`](ts-react-skel.md),
  [`flutter-skel.md`](flutter-skel.md),
  [`java-spring-skel.md`](java-spring-skel.md),
  [`rust-actix-skel.md`](rust-actix-skel.md),
  [`rust-axum-skel.md`](rust-axum-skel.md),
  [`python-django-skel.md`](python-django-skel.md),
  [`python-flask-skel.md`](python-flask-skel.md),
  [`js-skel.md`](js-skel.md).

### 2. The in-service code agent (`./ai`)

* [**LLM-MAINTENANCE.md § `./ai`**](LLM-MAINTENANCE.md#ai-service-local-ai-refactoring)
  — the full agent reference. Subcommands (`propose`, `apply`,
  `verify`, `explain`, `history`, `undo`, `upgrade`), the in-tree vs
  out-of-tree dispatch modes, the safety contract (git stash, path
  traversal rejection, per-service lock), the cross-call memory JSONL
  format.
* [**`../SERVICE_REFACTOR_COMMAND.md`**](../SERVICE_REFACTOR_COMMAND.md)
  — the original design doc for `./ai`. Canonical source for the
  runtime's internal invariants.

### 3. Template ↔ service sync (`./backport`, `./ai upgrade`)

* [**LLM-MAINTENANCE.md § `./backport`**](LLM-MAINTENANCE.md#backport-service-edits--template)
  — propose/apply CLI, the VERSION bump + CHANGELOG append on apply.
* [**LLM-MAINTENANCE.md § `./ai upgrade`**](LLM-MAINTENANCE.md#skeleton-versioning--ai-upgrade-since-2026-04)
  — sidecar layout, version comparison rules, changelog excerpt
  extraction, propose/apply dispatch.
* [**`../SKEL_BACKPORT_COMMAND.md`**](../SKEL_BACKPORT_COMMAND.md) —
  original design doc for `./backport`.
* [**`../UPDATE_SKEL_REFACTOR.md`**](../UPDATE_SKEL_REFACTOR.md) —
  original design doc for `./ai upgrade`.

### 4. Operator reference

* [**MAKEFILE.md**](MAKEFILE.md) — every Make target grouped by
  purpose (gen, test, AI smokes, cross-stack HTTP tests, sync).
* [**DEPENDENCIES.md**](DEPENDENCIES.md) — per-stack toolchains,
  Ollama setup, optional FAISS/RAG deps.
* [**JUNIE-RULES.md**](JUNIE-RULES.md) — project-authoritative
  behavior rules (what every agent must / must not do).
* [**`../AGENTS.md`**](../AGENTS.md) — cross-agent baseline (applies
  to Claude Code, Cursor, Aider, Junie, etc.).
* [**`../CLAUDE.md`**](../CLAUDE.md) — Claude Code-specific
  conventions (Plan/Task tooling, memory hygiene).

---

## Quick tour

```bash
# 0) Toolchains (one-time)
./skel-deps --all
ollama serve &
ollama pull gemma4:31b

# 1) Generate a whole project via a single dialog
_bin/skel-gen-ai myproj

# 2) Every generated service ships ./ai, ./backport, and a VERSION sidecar
cd myproj
./services                          # items_api  web_ui  _shared
ls items_api/ai                     # per-service AI script
cat items_api/.skel_context.json    # { "skeleton_name": "…", "skeleton_version": "0.1.0" }

# 3) Fan-out ./ai at the project root
./ai "rename Item to Ticket"        # hits items_api AND web_ui
./ai items_api "fix the 404 path"   # scope to one service

# 4) Service ↔ template flow
./backport               # propose: service → template diff
./backport apply         # writes upstream; bumps skel VERSION; appends CHANGELOG
./ai upgrade             # pull skeleton changes back down
```

---

## What's NOT in this directory

* **Scratch/test artefacts** live under `_test_projects/` (gitignored).
  Regenerate with `make clean-test && make test-generators`.
* **AI manifests** live under
  [`../_skels/_common/manifests/<skel>.py`](../_skels/_common/manifests/)
  — documented at the top of
  [`../_bin/skel_ai_lib.py`](../_bin/skel_ai_lib.py).
* **Per-service AI memory** lives under
  `<wrapper>/.ai/memory.jsonl` and `<service>/.ai/memory.jsonl` in
  generated projects, not in this repo.

---

## Maintenance workflow

Running `./maintenance` (or the `make clean-test && make test-generators
&& ./test` triplet) is the canonical pre-commit check. The GitHub
Actions workflow `.github/workflows/maintenance.yml` runs the same
triplet on every push to `master`.

For AI-pipeline changes specifically:

* `make test-ai-generators-dry` — always cheap (verifies dispatch +
  base scaffolding without calling Ollama).
* `make test-ai-generators` — slow (~30 min), requires a running
  Ollama. Exits with code `2` (skipped) when Ollama is unreachable so
  it's safe to call from longer scripts.
* `make test-ai-script` / `test-ai-memory` / `test-ai-upgrade` /
  `test-ai-fanout` / `test-backport-script` — fast no-LLM smokes that
  exercise the per-service agent, the memory plumbing, the upgrade
  paths, the wrapper fan-out, and the backport round trip.

See [MAKEFILE.md § AI targets](MAKEFILE.md#ai-pipeline-targets) for
the complete list.
