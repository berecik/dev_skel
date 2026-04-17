# Dev Skel

**Dev Skel generates whole multi-service projects where every service ships
with its own in-service code agent.**

You ask once, in plain English. Ollama writes the backend, writes the
frontend, wires them together over a shared `/api/items` + `/api/auth`
contract, runs the test suite, repairs whatever breaks, and writes the
docs. Each generated service then ships its **own** `./ai` script — a
local refactor agent backed by FAISS retrieval, the same fix-loop, and
a git-stash safety net — so you keep talking to the project after it
exists. Templates and services stay in sync via `./backport` (service →
template, with VERSION + CHANGELOG bump) and `./ai upgrade` (template →
service).

There are 12 skeletons in the catalogue — FastAPI, FastAPI-RAG,
Django, Django-Bolt, Flask, Spring, Actix, Axum, Go, Node, React/Vite,
and Flutter. Any combination can be generated into one wrapper that
shares its database, JWT secret, and service-URL map. Ten of them
ship full AI manifests so `skel-gen-ai` can rewrite them; the
remaining two (`go-skel`, `python-fastapi-rag-skel`) work via the
static path today and gain manifests as they mature.

---

## The three AI surfaces

| Surface | Direction | Where it runs | What it does |
| ------- | --------- | ------------- | ------------ |
| **`_bin/skel-gen-ai`** | template → new project | dev_skel checkout | Full-stack dialog → backend + frontend → integration phase → test-and-fix loop → docs |
| **`./ai`** (per service) | service → service | inside the generated service | Natural-language refactors with FAISS retrieval, fix-loop verify, git-stash undo, project-shared memory |
| **`./backport` + `./ai upgrade`** | service ↔ template | inside the generated service | Promote service edits up to the skeleton (`./backport`); pull skeleton changes back down (`./ai upgrade`) |

A wrapper-level `./ai` lives at the project root and **fans out to every
service by default** (`./ai "REQUEST"`); pass a slug (`./ai web_ui
"REQUEST"`) to scope to one. Same for `./ai upgrade` and `./backport`.

---

## Five-minute tour

```bash
# 0) One-time setup
ollama serve &                # in another terminal
ollama pull qwen3-coder:30b        # ~19 GB; default model

# 1) Generate a full-stack project from a single dialog
_bin/skel-gen-ai myproj
#  Step 1/6: Backend  [default: python-django-bolt-skel]
#  Step 2/6: Frontend [default: ts-react-skel]
#  Step 3/6: Service display names …
#  Step 4/6: Main CRUD entity (e.g. ticket)
#  Step 5/6: Auth style (jwt / session / oauth / …)
#  Step 6/6: Three custom prompts (backend / frontend / integration)
#
# Then Ollama runs four phases:
#   Phase 1: backend overlay   (rewrites the manifest's "core" files for the chosen entity)
#   Phase 2: frontend overlay  (same, on the React/Flutter side)
#   Phase 3: integration       (cross-service glue, wrapper-snapshot-aware)
#   Phase 4: test-and-fix      (./test → ask Ollama to repair → re-run, capped by fix_timeout_m)
#   Phase 5: documentation     (per-service AGENTS.md / CLAUDE.md / README.md)

cd myproj
./services                    # items_api / web_ui / _shared
./run web_ui dev              # npm run dev
./test                        # fans out across every service

# 2) Talk to the running project
./ai "rename Item to Ticket and add a 'priority' enum field"
#   wrapper-level ./ai = fan-out: this single request reaches the
#   backend service AND the React frontend in one go.
./ai apply "rename Item to Ticket and add a 'priority' enum field"
#   apply: writes the diff, runs ./test in each service, fix-loops on
#   failure, rolls back from a git stash if the fix loop times out.

# 3) Promote the change back to the template so future projects inherit it
./backport propose            # show the service-vs-skeleton diff
./backport apply              # write changes upstream + bump VERSION + append CHANGELOG entry

# 4) Months later — pull skeleton bug-fixes into this project
./ai upgrade                  # dry-run: shows the v0.4.2 → v0.5.0 changelog excerpt
./ai upgrade --apply          # apply, fix-loop, rewrite sidecar's skeleton_version
```

That's the whole loop. Everything below is detail.

---

## Generation: `_bin/skel-gen-ai`

`skel-gen-ai` is a multi-phase Ollama orchestrator backed by a local
FAISS RAG index of every skeleton's reference templates (`_bin/skel_rag/`,
default embedding model `BAAI/bge-small-en-v1.5`).

### Modes

* **Full-stack mode** (default — no positional `skel_name`):
  asks for **backend** and **frontend** separately. Both halves are
  optional: `--no-frontend` for backend-only, `--no-backend` for
  frontend-only. The dialog refuses the "neither" combination.
* **Single-skel mode** (legacy): pass a positional skeleton name to
  rewrite just that one skel.

```bash
# Interactive full-stack
_bin/skel-gen-ai                     # cwd as wrapper
_bin/skel-gen-ai myproj              # fresh wrapper directory

# Fully scripted (CI-friendly)
_bin/skel-gen-ai myproj \
    --backend python-fastapi-skel \
    --frontend ts-react-skel \
    --backend-service-name "Items API" \
    --frontend-service-name "Web UI" \
    --item-name ticket \
    --auth-type jwt \
    --backend-extra "use refresh tokens with 2 hour TTL" \
    --frontend-extra "use Tailwind CSS" \
    --integration-extra "add a smoke test that hits /api/items via fetch" \
    --no-input

# Backend-only
_bin/skel-gen-ai myproj --no-frontend --backend python-fastapi-skel
# Frontend-only
_bin/skel-gen-ai myproj --no-backend  --frontend ts-react-skel
# Dry-run (no Ollama, no writes; verifies dispatch + base scaffolding)
_bin/skel-gen-ai myproj --no-input --dry-run
```

### What the dialog asks

| Step | Question | Default |
| ---- | -------- | ------- |
| 1 | Backend skeleton | first backend that ships `/api/items` (currently `python-django-bolt-skel`) |
| 2 | Frontend skeleton | **`ts-react-skel`** (since 2026-04) |
| 3 | Service display names | `Items API` + `Web UI` (slugified to `items_api/` + `web_ui/`) |
| 4 | Main CRUD entity | `item` → becomes `{item_class}` / `{items_plural}` in every manifest prompt |
| 5 | Auth style | `jwt` (`none`/`basic`/`session`/`jwt`/`oauth`/`api_key`) |
| 6 | Three custom prompts | `backend_extra` / `frontend_extra` / `integration_extra` placeholders, each piped into the matching phase |

### Five phases per run

1. **Backend overlay** — rewrites the files listed in
   `_skels/_common/manifests/<backend>.py` for the chosen entity.
2. **Frontend overlay** — same on the frontend side.
3. **Integration** — backend manifest's `INTEGRATION_MANIFEST` runs
   with the frontend visible as a sibling; writes typed clients +
   integration tests.
4. **Test-and-fix loop** — runs `./test` in the integration scope; on
   failure, asks Ollama to repair each failing file in turn, then
   re-runs. Bounded by `fix_timeout_m` (default 120 min).
5. **Documentation** — per-service `AGENTS.md`, `CLAUDE.md`,
   `README.md` rendered against the now-live service.

Skip individual phases with `--no-integrate`, `--no-test-fix`,
`--no-docs`. Disable the backend or frontend half entirely with
`--no-backend` / `--no-frontend`.

### Ollama configuration

| Env | Default | Notes |
| --- | ------- | ----- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `qwen3-coder:30b` | drop to `qwen2.5-coder:7b` on slow hardware |
| `OLLAMA_TIMEOUT` | `1800` (s) | sized for a 30 B-class model + cold load |

CLI overrides: `--ollama-url`, `--ollama-model`, `--fix-timeout-m`,
`--max-files`.

### Adding a new skeleton

1. Drop the skeleton tree under `_skels/<name>-skel/`.
2. Add a manifest at `_skels/_common/manifests/<name>-skel.py` listing
   the files Ollama should generate (placeholders documented at the top
   of `_bin/skel_ai_lib.py`). The full-stack dialog auto-discovers it.
3. Optionally declare an `INTEGRATION_MANIFEST` for the cross-service
   wiring phase.

---

## In-service code agent: `./ai`

Every generated service ships `./ai` and `.ai_runtime.py`. The runtime
auto-detects two modes:

* **In-tree** — dev_skel checkout reachable. Imports
  `skel_rag.agent.RagAgent` (FAISS + sentence-transformers) and the
  shared fix-loop from `skel_ai_lib`. Same call stack as `skel-gen-ai`.
* **Out-of-tree** — service detached from dev_skel. Stdlib-only
  retrieval (ripgrep with a pathlib fallback) + a bundled minimal
  fix-loop. No third-party imports beyond the Python stdlib + a single
  `urllib.request` call to Ollama.

```
./ai "REQUEST"               # propose, dry-run (writes .ai/<ts>-<sha>/)
./ai apply "REQUEST"         # propose + apply + verify (fix loop)
./ai verify                  # re-run last proposal's fix loop
./ai explain                 # last run's per-file rationale
./ai history                 # past runs (project + local sections)
./ai undo                    # revert last applied refactor (git stash)
./ai upgrade                 # pull skeleton changes since gen time
./ai upgrade --apply         # commit them via the propose/apply flow
```

### Safety contract

Every `apply` is bounded:

* All writes are checked against `service_dir.resolve()` — paths
  outside (`../`, absolute paths, `.git`, `.ai`, `node_modules`,
  `.venv`) are rejected by both the LLM-output parser and the applier.
* `apply` refuses to run on a dirty git tree without `--allow-dirty`.
* Pre-apply state is captured to a git stash; verification failure
  triggers `git stash pop` to restore.
* Per-service `.ai/.lock` (`O_CREAT|O_EXCL`) prevents concurrent
  applies.

### Output layout

```
<service>/.ai/
├── <ts>-<sha>/
│   ├── request.txt              # the natural-language request
│   ├── context.json             # resolved RefactorContext
│   ├── retrieved/chunks.md      # FAISS retrieval block (in-tree mode)
│   ├── proposals/<rel>.proposed # one file per proposed edit
│   ├── rationale.md             # per-file rationale
│   ├── applied.json             # written only after --apply
│   └── verification.log         # written only after the fix-loop runs
├── HEAD                         # symlink to the latest run dir
├── memory.jsonl                 # per-service AI memory
└── .lock                        # per-service apply lock
```

`.ai/` is git-ignored. `<wrapper>/.ai/memory.jsonl` mirrors the same
log at the project level (see "Project-wide memory" below).

---

## Service ↔ template sync

Every skel ships a `VERSION` (semver) and a `CHANGELOG.md` (Keep a
Changelog). Each generated service stores its source skel version in a
sidecar `.skel_context.json` (`skeleton_version`).

### `./backport` — service → template

```
./backport          # propose (dry-run): list service files that differ from the skeleton
./backport apply    # write changes upstream + bump VERSION (semver patch) + append CHANGELOG entry
```

`./backport apply` is **how the changelog gets written**. Each entry
lists every backported file with its reason — making the changelog an
auditable, replayable log of every accepted service-to-template change.
The skeleton tree must be a reachable dev_skel checkout (auto-detected;
`$DEV_SKEL_ROOT` overrides).

### `./ai upgrade` — template → service

```
./ai upgrade        # dry-run: print v0.4.2 → v0.5.0 transition + CHANGELOG excerpt
./ai upgrade --apply  # synthesise an AI request from the changelog excerpt and apply it
```

Reads `skeleton_version` from the sidecar, compares to
`<skel>/VERSION`, extracts the matching CHANGELOG entries between the
two versions (semver-ordered), and synthesises a refactor request:
*"Upgrade this service from v0.4.2 to v0.5.0. The skeleton shipped these
changes since this service was generated: [excerpt]. Apply equivalent
changes to this service."* Dispatched through the standard
propose/apply path so all the safety machinery still applies. On
success the sidecar's `skeleton_version` is rewritten.

---

## Wrapper-level `./ai` (project-wide fan-out)

The wrapper auto-generates a top-level `./ai` script that **fans out by
default**:

```
./ai "REQUEST"             # runs the request against every service in the wrapper
./ai <slug> "REQUEST"      # scopes to one service
./ai upgrade               # upgrade every service to its skeleton's latest VERSION
./backport                 # propose the diff for every service
./backport apply           # apply every service's diff upstream
```

`--all` is the legacy explicit-fan-out flag — kept for backwards
compatibility with the pre-2026-04 single-by-default behavior.

### Project-wide memory

Every `./ai apply` appends a JSONL entry (request, edited files,
truncated rationale, pass/fail) to **both**
`<service>/.ai/memory.jsonl` AND `<wrapper>/.ai/memory.jsonl`.

The next `./ai propose` (in any service of the wrapper) prepends the
last 5 entries from the wrapper-shared log to the LLM prompt as a
`## PREVIOUS_AI_RUNS` block. So when the model edits the React
frontend, it sees what was just done in the FastAPI backend — and can
keep the contracts aligned without you re-explaining.

`./ai history` prints both layers (project memory + local scratch).

---

## What's in the box: skeletons

| Skeleton | Kind | AI manifest | Items API contract | Notes |
| -------- | ---- | ----------- | ------------------ | ----- |
| `python-fastapi-skel` | backend | ✓ | server | DDD layout, async SQLAlchemy, OpenAPI |
| `python-fastapi-rag-skel` | backend | — | partial | FastAPI variant with chroma + RAG endpoints |
| `python-django-skel` | backend | ✓ | server | Classic Django |
| `python-django-bolt-skel` | backend | ✓ | server | Django + Rust HTTP layer (~60k RPS) |
| `python-flask-skel` | backend | ✓ | server | Lightweight WSGI |
| `java-spring-skel` | backend | ✓ | server | Spring Boot 3 + JwtProperties bean |
| `rust-actix-skel` | backend | ✓ | server | Actix-web + AppState env wiring |
| `rust-axum-skel` | backend | ✓ | server | Axum + Tokio |
| `go-skel` | backend | — | server | net/http + sqlite + JWT |
| `next-js-skel` | backend | ✓ | server | Next.js 15 App Router + better-sqlite3 + jose JWT |
| `ts-react-skel` | frontend | ✓ | client | React 19 + Vite + typed `src/api/items.ts` |
| `flutter-skel` | frontend | ✓ | client | Flutter Material 3 + `flutter_secure_storage` + `flutter_dotenv` |

All 12 ship the `./ai` runtime (so generated services keep talking to
the model after they exist) plus a `VERSION` + `CHANGELOG.md` (so
`./backport` and `./ai upgrade` work). Every skeleton includes a
**Dockerfile** (multi-stage: builder → production → development),
**.devcontainer/** settings (VS Code Dev Containers with per-stack
extensions, Postgres backing service, port forwarding), and a
**.dockerignore**. Frontend skeletons (React, Flutter) ship an
`nginx.conf` for SPA routing in production. Backends marked **server**
ship the wrapper-shared `/api/items` + `/api/categories` +
`/api/auth` + `/api/state` contract;
both frontends call that contract out of the box.

---

## Wrapper-shared environment

Every backend reads `<wrapper>/.env` first, then its local `.env`. The
shared keys are:

```ini
# Database — every backend points at the same store
DATABASE_URL=sqlite:///_shared/db.sqlite3
DATABASE_JDBC_URL=jdbc:sqlite:_shared/db.sqlite3
SPRING_DATASOURCE_URL=jdbc:sqlite:_shared/db.sqlite3

# JWT — same secret across services so a token issued by one is accepted by all
JWT_SECRET=change-me-32-bytes-of-random-data
JWT_ALGORITHM=HS256
JWT_ISSUER=devskel
JWT_ACCESS_TTL=3600
JWT_REFRESH_TTL=604800

# Default backend URL the frontends call
BACKEND_URL=http://localhost:8000
```

`<wrapper>/_shared/service-urls.env` is auto-regenerated on every
`gen` with one `SERVICE_URL_<UPPER_SLUG>=http://...` per service so
handlers can call siblings via `os.environ['SERVICE_URL_AUTH_API']`
(Python), `process.env.SERVICE_URL_AUTH_API` (Node),
`${SERVICE_URL_AUTH_API}` (Spring), or
`std::env::var("SERVICE_URL_AUTH_API")` (Rust).

To switch the wrapper from SQLite to Postgres, edit `.env` and update
all three `DATABASE_*` URL variants in lockstep, then run
`./install-deps && ./test`. Every service picks up the change on the
next restart — no per-service edits needed.

---

## Static fallback (no Ollama)

`_bin/skel-gen-static` is the deterministic, AI-free path. Same
positional CLI as `skel-gen-ai`, no Ollama required, no overlay phase —
useful for CI without a model server, or when you want a baseline you
can diff against an AI-generated overlay.

```bash
_bin/skel-gen-static myproj python-fastapi-skel "Items API"
_bin/skel-gen-static --existing-project myproj ts-react-skel "Web UI"
```

`_bin/skel-gen` is a thin dispatcher: it execs `skel-gen-ai` by default
and `skel-gen-static` when `--static` is passed. `_bin/skel-add` is the
existing-wrapper sibling; same positional layout, defaults to AI mode
via `skel-gen-ai --skip-base`.

---

## Install dev_skel locally (`~/dev`)

Dev Skel keeps **two** copies of itself on your machine:

| Path | Role |
| ---- | ---- |
| `~/dev_skel` (`SKEL_DIR`) | The git checkout — what you `git pull` and edit. |
| `~/dev` (`DEV_DIR`) | The installed copy you run from. `_bin/skel-install` rsyncs the checkout here so generators / scripts land on a stable, edit-free path. |

Both defaults can be overridden via env vars or `~/.dev_skel.conf`.

### First-time install

```bash
git clone https://github.com/<you>/dev_skel ~/dev_skel
cd ~/dev_skel

# Copy the checkout into ~/dev (creates the directory if missing)
_bin/skel-install
# > Installing dev skeleton to /Users/you/dev...
# > Install complete!
```

After this you can run dev_skel from either location. `~/dev` is the
"production" copy; you typically `cd ~/dev` to generate projects, and
edit the templates from `~/dev_skel`.

### Pull updates

When you `git pull` in `~/dev_skel`, mirror the changes into `~/dev`:

```bash
cd ~/dev_skel
git pull
_bin/skel-update
# rsync -av --progress  ~/dev_skel/ → ~/dev/
```

`skel-update` requires `~/dev` to already exist (run `skel-install`
first if it doesn't). The rsync honors two exclude lists
(`_bin/rsync-common-excludes.txt` for build artefacts,
`_bin/rsync-update-excludes.txt` for files you want to keep across
updates) so it never clobbers `~/dev/.dev_skel.conf`, your
`_test_projects/`, or any other live state.

### Override the defaults

```bash
# Per-shell — use a different install location
DEV_DIR=~/projects/dev_skel_runtime _bin/skel-install

# Pointing at a different checkout (e.g. a fork)
SKEL_DIR=~/code/dev_skel-fork _bin/skel-install

# Persist via ~/.dev_skel.conf (shell-style)
cat > ~/.dev_skel.conf <<'EOF'
SKEL_DIR=$HOME/code/dev_skel
DEV_DIR=$HOME/projects/dev_skel_runtime
EOF
_bin/skel-install            # uses the conf values from now on
```

The complete list of env vars / conf keys lives in
`_bin/dev_skel_lib.py::_default_env`.

### Optional: sync to a remote host

```bash
SYNC_SSH_HOST=devbox SYNC_DEST_DIR=/srv/dev_skel _bin/skel-sync
# rsync -az --delete --progress -e ssh ~/dev_sync/ → devbox:/srv/dev_skel/
```

Useful for keeping a remote dev box in lockstep with your local
checkout.

---

## Requirements

* **Python 3.10+** (the CLIs and the in-service runtime)
* **[Ollama](https://ollama.ai/)** + a model (default `qwen3-coder:30b`)
* **Per-stack toolchains** — installed via `./skel-deps`:
  * Python 3.10+ (pip + venv)
  * Node 20+ (npm)
  * JDK 21+ (Maven)
  * Rust stable (Cargo via rustup)
  * Flutter SDK (optional — only for `flutter-skel`)
  * GNU Make 4+

```bash
./skel-deps --list           # what's needed per skel + install status
./skel-deps --all            # install everything for every skeleton
./skel-deps python-fastapi   # one stack only
make install-rag-deps        # in-tree FAISS deps (sentence-transformers, faiss-cpu, langchain-ollama)
```

The in-service `./ai` works **without** the FAISS deps in out-of-tree
mode (stdlib-only retrieval + minimal fix loop). The full RAG pipeline
is only needed when running from inside a dev_skel checkout.

---

## Doc map

| When you need to … | Read |
| ------------------ | ---- |
| Drive `skel-gen-ai`, `./ai`, `./backport`, `./ai upgrade` | [`AGENTS.md`](AGENTS.md) (cross-agent) and [`CLAUDE.md`](CLAUDE.md) (Claude-specific) |
| Maintain or extend the AI pipeline (manifests, RAG agent, fix loop) | [`_docs/LLM-MAINTENANCE.md`](_docs/LLM-MAINTENANCE.md) |
| Look up Make targets (gen, test, AI smokes, sync) | [`_docs/MAKEFILE.md`](_docs/MAKEFILE.md) |
| Survey the 12 skeletons + their AI manifests | [`_docs/SKELETONS.md`](_docs/SKELETONS.md) |
| Install dev_skel into `~/dev` (or anywhere) | this section above + [`_docs/DEPENDENCIES.md`](_docs/DEPENDENCIES.md) |
| Install per-stack toolchains + Ollama | [`_docs/DEPENDENCIES.md`](_docs/DEPENDENCIES.md) |
| Project-authoritative behavior rules | [`_docs/JUNIE-RULES.md`](_docs/JUNIE-RULES.md) |
| Per-skeleton deep-dive | [`_docs/<skel>.md`](_docs/) |
| Create or update a skeleton | [`_docs/SKELETON-DESIGN-GUIDE.md`](_docs/SKELETON-DESIGN-GUIDE.md) |
| Design specs (originals) | [`SERVICE_REFACTOR_COMMAND.md`](SERVICE_REFACTOR_COMMAND.md), [`SKEL_BACKPORT_COMMAND.md`](SKEL_BACKPORT_COMMAND.md), [`UPDATE_SKEL_REFACTOR.md`](UPDATE_SKEL_REFACTOR.md) |

---

## Smoke tests (no Ollama needed)

| Target | What it covers |
| ------ | -------------- |
| `make test-ai-script` | `./ai` dispatches into the runtime, writes scratch artefacts, history works |
| `make test-ai-memory` | Wrapper-level `./ai` dispatches into per-service `./ai`; project memory round-trips |
| `make test-ai-upgrade` | `./ai upgrade` no-op (current version) and outdated paths |
| `make test-ai-fanout` | Wrapper `./ai` fans out across two services by default |
| `make test-backport-script` | `./backport propose` + `apply` round trip; VERSION bumped + CHANGELOG entry written |
| `make test-shared-db` | Every backend sees the wrapper-shared SQLite via `DATABASE_URL` |
| `make test-react-django-bolt` / `test-react-fastapi` / … | Cross-stack HTTP exercise of the full `register → login → CRUD → complete` flow |

The full LLM-driven pipeline lives behind `make test-ai-generators`
(slow — ~30 minutes total — and skips with exit code `2` when Ollama is
unreachable).

---

## GitHub CI/CD pipeline

The repository ships a single GitHub Actions workflow
(`.github/workflows/maintenance.yml`) that runs the full maintenance
suite on every push / PR to `master`: Python 3.11, Node 20, JDK 21,
Rust stable, uv — then `./maintenance` (which is `make clean-test &&
make test-generators && ./test`).

Three Make targets expose the pipeline status locally via `gh`:

```bash
make ci-status   # list recent runs (last 10)
make ci-watch    # tail the latest run in real time (blocks until done)
make ci-log      # dump the full log of the most recent run
```

All three require the GitHub CLI (`brew install gh`) and a one-time
`gh auth login`. They print actionable errors when either is missing.

---

## License

This repo is the skeleton generator. Generated projects inherit each
framework's license terms.
