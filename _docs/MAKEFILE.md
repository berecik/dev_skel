# Makefile Reference

The top-level `Makefile` orchestrates two parallel pipelines:

* **Static generators** — one `gen-<framework>` target per skeleton,
  delegating to the per-skel `gen` script. Used for AI-free baselines
  and for the `test-generators` smoke that runs in CI without a model
  server.
* **AI pipeline** — `test-ai-*` targets that exercise the
  `skel-gen-ai` orchestrator, the in-service `./ai` runtime, the
  `./backport` round-trip, the `./ai upgrade` flow, and the
  wrapper-level fan-out behavior.

Plus a handful of cross-stack HTTP integration tests that pair a
backend with a frontend and exercise the full `register → login → CRUD
→ complete` flow over real ports.

---

## AI pipeline targets

These are the **AI-first** targets — they exercise the surfaces that
make this project distinctive. Most are no-LLM smokes (cheap, run on
every CI machine); the slow real-Ollama runners are clearly marked.

### Per-service `./ai` agent

| Target | LLM? | What it covers |
| ------ | ---- | -------------- |
| `make test-ai-script` | no | `./ai` dispatches into the runtime, scratch dir + `request.txt` + `context.json` are populated, `./ai history` lists the run. |
| `make test-ai-script-keep` | no | Same, leaves the wrapper on disk under `_test_projects/`. |
| `make test-ai-memory` | no | Wrapper-level `./ai` dispatches into per-service `./ai`; project-wide memory round-trips through `<wrapper>/.ai/memory.jsonl` AND `<service>/.ai/memory.jsonl`; `./ai history` aggregates both layers. |

### `./ai upgrade` (template → service)

| Target | LLM? | What it covers |
| ------ | ---- | -------------- |
| `make test-ai-upgrade` | no | No-op upgrade (sidecar version matches skel) returns "nothing to upgrade". Outdated upgrade (synthetic VERSION bump) surfaces the `vX → vY` transition + CHANGELOG excerpt and dispatches through the propose path. Sidecar is left untouched on dry-run. |
| `make test-ai-upgrade-keep` | no | Same, keeps the wrapper. |

### Wrapper-level fan-out

| Target | LLM? | What it covers |
| ------ | ---- | -------------- |
| `make test-ai-fanout` | no | Generates a wrapper with two services. `./ai "..."` at wrapper root hits both. `./ai <slug> "..."` scopes to one. `./ai upgrade` (no-op) fans out to both. |
| `make test-ai-fanout-keep` | no | Same, keeps the wrapper. |

### `./backport` (service → template)

| Target | LLM? | What it covers |
| ------ | ---- | -------------- |
| `make test-backport-script` | no | Generates a service, modifies one file, runs `./backport propose` (asserts the file appears in the diff), runs `./backport apply` (asserts the skel template was updated, **VERSION** was bumped, and **CHANGELOG.md** got a new entry). Restores the skel state on teardown. |
| `make test-backport-script-keep` | no | Same, keeps the wrapper. |

### Real Ollama tests

These need a running Ollama daemon. They exit with code `2`
(treated as "skipped") when Ollama is unreachable, so they're safe to
call from longer scripts.

| Target | LLM? | What it covers |
| ------ | ---- | -------------- |
| `make test-ai-generators-dry` | no | Verifies dispatch + base scaffolding for every AI-supported skel without calling Ollama. **Run this first** when changing a manifest. |
| `make test-ai-generators` | **yes** | Slow (~30 min total). Runs the entire `skel-gen-ai` pipeline (Phase 1 backend overlay + Phase 2 frontend overlay + Phase 3 integration + Phase 4 test-and-fix + Phase 5 docs) per skel. |
| `make test-gen-ai-<framework>` | **yes** | One skel at a time (e.g. `test-gen-ai-fastapi`, `test-gen-ai-django-bolt`). |

### Sync the in-service runtime

| Target | What it does |
| ------ | ------------ |
| `make sync-ai-runtime` | Copies the canonical `_bin/dev_skel_refactor_runtime.py` into `_skels/_common/refactor_runtime/` so newly-generated services pick up runtime changes. **Run after editing the runtime.** |

### Install RAG dependencies

| Target | What it does |
| ------ | ------------ |
| `make install-rag-deps` | Installs the optional in-tree FAISS deps (`sentence-transformers`, `faiss-cpu`, `langchain-ollama`). Required for in-tree `./ai` mode and for `skel-gen-ai`'s `{retrieved_context}` / `{retrieved_siblings}` placeholders. The out-of-tree `./ai` mode works without these. |

---

## Cross-stack HTTP integration tests

Each one generates a wrapper containing a backend + a frontend skel,
rewrites `BACKEND_URL` to a non-conflicting port, builds the frontend,
runs migrations (where applicable), starts the backend, and exercises
the canonical 9-step `register → login → CRUD → complete` flow over
real HTTP. Skips gracefully when the required toolchain is missing.

### React + backend

| Target | Backend |
| ------ | ------- |
| `make test-react-django-bolt` | `python-django-bolt-skel` (canonical pair, ~3 min cold) |
| `make test-react-fastapi` | `python-fastapi-skel` (~1 min) |
| `make test-react-django` | `python-django-skel` |
| `make test-react-flask` | `python-flask-skel` |
| `make test-react-spring` | `java-spring-skel` |
| `make test-react-actix` | `rust-actix-skel` |
| `make test-react-axum` | `rust-axum-skel` |
| `make test-react-go` | `go-skel` |
| `make test-react-nextjs` | `next-js-skel` (Next.js 15) |

Each has a `-keep` sibling that leaves the wrapper on disk for
debugging. Pass `--port <N>` to override the backend port.

### Flutter + backend

| Target | Backend |
| ------ | ------- |
| `make test-flutter-django-bolt` | `python-django-bolt-skel` |
| `make test-flutter-fastapi` | `python-fastapi-skel` |
| `make test-flutter-cross-stack` | both, sequentially |

Skips when the Flutter SDK isn't on the PATH.

### Cross-language shared DB

| Target | What it covers |
| ------ | -------------- |
| `make test-shared-db` | Generates a wrapper containing every backend skel, seeds `<wrapper>/_shared/db.sqlite3`, asserts each backend reads the seed row through the env-driven flow. Cross-stack round-trip: writes via one Python service's venv, reads from another. Auto-skips toolchains that aren't installed. |
| `make test-shared-db-python` | Same, but Python-only (~25 s). |
| `make test-shared-db-keep` | Keeps the wrapper. |

### AI-generation integration test (Pizzeria)

| Target | What it covers |
| ------ | -------------- |
| `make test-pizzeria-orders` | Generates a FastAPI + Flutter pizzeria ordering app via `skel-gen-ai` with domain-specific prompts, then exercises the full order lifecycle (menu → positions → order → address → submit → approve/reject → feedback) over real HTTP. Requires Ollama. Flutter optional. |
| `make test-pizzeria-orders-keep` | Same, keeps `_test_projects/test-pizzeria-orders` on disk. |

Exits with code 2 when Ollama is unreachable. Falls back to backend-only
when Flutter SDK is missing. See `_docs/PIZZERIA-TEST-PLAYBOOK.md`.

| Target | What it covers |
| ------ | -------------- |
| `make test-cross-stack` | Aggregator — every cross-stack HTTP test in one run. |

---

## Static generator targets

The pre-AI baseline. All accept `NAME=<wrapper>` plus an optional
`SERVICE=<display-name>`.

| Target | Skeleton | Default service slug |
| ------ | -------- | -------------------- |
| `make gen-fastapi NAME=<w>` | `python-fastapi-skel` | `backend/` |
| `make gen-fastapi-rag NAME=<w>` | `python-fastapi-rag-skel` | `backend/` |
| `make gen-django NAME=<w>` | `python-django-skel` | `backend/` |
| `make gen-django-bolt NAME=<w>` | `python-django-bolt-skel` | `backend/` |
| `make gen-flask NAME=<w>` | `python-flask-skel` | `backend/` |
| `make gen-spring NAME=<w>` | `java-spring-skel` | `service/` |
| `make gen-actix NAME=<w>` | `rust-actix-skel` | `service/` |
| `make gen-axum NAME=<w>` | `rust-axum-skel` | `service/` |
| `make gen-go NAME=<w>` | `go-skel` | `service/` |
| `make gen-nextjs NAME=<w>` | `next-js-skel` | `app/` |
| `make gen-react NAME=<w>` | `ts-react-skel` | `frontend/` |
| `make gen-flutter NAME=<w>` | `flutter-skel` | `frontend/` |

These dispatch into each skel's `gen` script via `bash $(GEN)`. The
**relocatable** sibling — `_bin/skel-gen-static` — accepts the same
positional `[proj_name] [skel_name] [service_name]` layout and works
from any directory.

```bash
make gen-fastapi NAME=myproj SERVICE="Auth API"   # → myproj/auth_api/
_bin/skel-gen-static myproj python-fastapi-skel "Auth API"   # equivalent
```

### Per-skel test targets

| Target | What it does |
| ------ | ------------ |
| `make test-generators` | Generates a project from every skel, runs basic import/build checks. **No Ollama required.** Runs in CI. |
| `make test-gen-<framework>` | One skel only (e.g. `test-gen-fastapi`). |
| `make test-all` | Runs each skel's own `bash ./test` (its end-to-end self-test). |
| `make test-<framework>` | One skel's self-test. |
| `make clean-test` | Wipes `_test_projects/`. |

### Maintenance

| Target | What it does |
| ------ | ------------ |
| `make help` | Lists every target with descriptions. |
| `make list` | Lists discovered skeletons. |
| `make status` | Shows which skeleton directories exist. |
| `make info-all` | Per-skel info dumps. |
| `make clean-all` | Wipes per-skel build artefacts. |

The `./maintenance` shell script (at the repo root) runs `make
clean-test && make test-generators && ./test` — the canonical
pre-commit triplet, also wired into
`.github/workflows/maintenance.yml`.

---

## Per-skel Makefile structure

Each `_skels/<name>-skel/Makefile` is auto-discovered. The structure is:

```makefile
.PHONY: gen test

# Auto-detect skeleton directory regardless of where make is called from
SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

GEN := $(SKEL_DIR)/gen
MERGE := $(SKEL_DIR)/merge

gen: ## Generate project (NAME=myapp [SERVICE="Display Name"])
ifndef NAME
	@echo "Usage: make gen NAME=<project-name>"
	@exit 1
endif
	@bash $(GEN) "$(NAME)"

test: ## Generate a temp project and run its tests (e2e)
	@bash ./test
```

The `gen` Bash script is the source of truth — it scaffolds the
service tree, calls `merge` (rsync with exclusions), then invokes
`_skels/_common/common-wrapper.sh` to install the shared layer + the
in-service `./ai` machinery.

---

## Adding a new skeleton

1. Create `_skels/<name>-skel/` with a working source tree.
2. Add `gen`, `merge`, `test`, `deps` Bash scripts (copy from a
   similar skel and adjust).
3. Add `VERSION` (`0.1.0`) and `CHANGELOG.md` (Keep-a-Changelog seed).
4. Add the per-skel `Makefile` (template above).
5. Wire into the top-level Makefile:
   ```makefile
   NEW_SKEL := $(SKEL_DIR)/<name>-skel
   gen-<name>: ## Generate <Name> project (NAME=...)
       @bash $(NEW_SKEL)/gen "$(NAME)"
   test-gen-<name>: ## Test <Name> generator
       @bash $(NEW_SKEL)/test
   ```
6. (For AI support) drop a manifest at
   `_skels/_common/manifests/<name>-skel.py`. The full-stack dialog
   auto-discovers it.
7. Run `make test-generators` (no Ollama) and
   `make test-ai-generators-dry` to verify dispatch.

---

## GitHub CI/CD pipeline targets

The repository ships `.github/workflows/maintenance.yml` — a single
workflow that runs `./maintenance` (the `make clean-test && make
test-generators && ./test` triplet) on every push / PR to `master`,
with Python 3.11, Node 20, JDK 21, Rust stable, and uv pre-installed.

Three Make targets wrap the GitHub CLI (`gh`) for local inspection:

| Target | What it does |
| ------ | ------------ |
| `make ci-status` | List the 10 most recent CI runs (`gh run list`). Shows workflow name, branch, status, conclusion, duration. |
| `make ci-watch` | Tail the latest CI run in real time (`gh run watch`). Blocks until the run finishes — useful after pushing. |
| `make ci-log` | Dump the full log of the most recent CI run (`gh run view --log`). Useful for debugging failures without opening a browser. |

**Prerequisites**: `gh` installed (`brew install gh`) and authenticated
(`gh auth login`). Each target checks both conditions and prints an
actionable error when either is missing.
