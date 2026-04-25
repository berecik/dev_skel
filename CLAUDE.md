# Claude Code Rules — `dev_skel`

This file is the entrypoint Claude Code loads automatically. It is the
Claude-specific complement to `/AGENTS.md`. Everything in `/AGENTS.md`,
`_docs/JUNIE-RULES.md`, and `_docs/LLM-MAINTENANCE.md` still applies — read
them first and follow them. Sections below add behaviour that is specific to
Claude Code (slash commands, the Plan / Task tooling, persistent memory,
etc.).

When `/AGENTS.md` and this file disagree, prefer the **most restrictive**
guidance unless the user explicitly overrides it. When in doubt, ask.


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

## 1. Read These Files First (in order)

1. `/CLAUDE.md` (this file)
2. `/AGENTS.md` (cross-agent baseline)
3. `_docs/JUNIE-RULES.md` (project-authoritative rules)
4. `_docs/LLM-MAINTENANCE.md` (operational workflows)
5. `_docs/README.md` (documentation index)

When working on a specific skeleton (for example `python-fastapi-skel`), also
load:

6. `_skels/<name>/CLAUDE.md` (if present) **or** `_skels/<name>/AGENTS.md`
7. `_skels/<name>/JUNIE-RULES.md`
8. The skeleton page in `_docs/` (e.g. `_docs/python-fastapi-skel.md`)

Refresh these files whenever the user says rules/docs changed or after you
make rule-affecting edits.

---

## 2. Project Snapshot for Claude

- **One-line elevator pitch:** Dev Skel generates whole multi-service
  projects where every service ships with its own in-service code
  agent (`./ai`). Three AI surfaces — `skel-gen-ai` (template → new
  project), `./ai` (per-service refactor agent), `./backport` +
  `./ai upgrade` (service ↔ template sync, with VERSION/CHANGELOG
  automation). The wrapper-level `./ai` fans out across services by
  default.
- Multi-skeleton, Makefile-driven project generator. Each skeleton lives in
  `_skels/<lang>-<framework>-skel/` and produces a framework-specific service
  inside a wrapper project.
- **Service directories are named after the service display name.** When a
  user (or the AI dialog) supplies a name like `"Ticket Service"`, the
  on-disk directory becomes `myproj/ticket_service/`. Slugification is in
  `dev_skel_lib.slugify_service_name()`. Auto-suffix (`-1`, `-2`) only kicks
  in when the slug already exists in the wrapper.
- **Wrappers integrate services around a shared layer:**
  - `<wrapper>/.env` — single source of truth for `DATABASE_URL`,
    `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
    `JWT_REFRESH_TTL`. Sourced by every wrapper script before delegating.
  - `<wrapper>/_shared/db.sqlite3` — default shared SQLite database
    (swap to Postgres via `DATABASE_URL`).
  - `<wrapper>/services` — discovery script listing every service.
  - `<wrapper>/run|test|build|stop|install-deps` — multi-service dispatch
    wrappers; each accepts an optional first arg matching a service slug.
- The relocatable CLI (`_bin/skel-gen`, `_bin/skel-gen-ai`,
  `_bin/skel-gen-static`, `_bin/skel-add`, `skel-install`, `skel-update`,
  `skel-sync`, `skel-list`) is **Python**, sharing logic via
  `_bin/dev_skel_lib.py`. The legacy `_bin/common.sh` is kept only
  for backwards compatibility — do not extend it.
- **`_bin/skel-gen` defaults to AI (as of 2026-04).** It is a thin
  dispatcher that exec's `_bin/skel-gen-ai` by default, or
  `_bin/skel-gen-static` when `--static` is passed. The previous
  static-only behavior is preserved verbatim under `_bin/skel-gen-static`
  (the pre-2026-04 `skel-gen` content). Three explicit entrypoints:
  - **`_bin/skel-gen`** — canonical, AI by default.
  - **`_bin/skel-gen-ai`** — explicit AI (single name pinned for scripts).
  - **`_bin/skel-gen-static`** — explicit no-Ollama fallback.
- **`_bin/skel-add`** is the existing-wrapper sibling of `skel-gen`.
  It keeps the same positional order (`[proj_name] [skel_name]
  [service_name]`) but requires the wrapper to exist already. Default
  mode is AI (`_bin/skel-gen-ai --skip-base`), so the new service still
  runs the sibling integration, test-fix, and docs phases; `--static`
  forwards to `_bin/skel-gen-static --existing-project`.
- **CLI positional order** for all three entrypoints is
  `[proj_name] [skel_name] [service_name]` — all three are optional.
  Pass `.` (or omit) as `proj_name` to install into the current
  directory; the project's display name then comes from the cwd basename.
  Omitting `skel_name` in **static mode** falls into a single-skeleton
  picker; omitting it in **AI mode** triggers the new full-stack
  dialog (backend + frontend + three custom prompts). All CLIs detect
  the common "swapped argument" mistake (passing a `*-skel` name in
  the project slot) and bail with an actionable error.
- `_bin/skel-gen-ai` is the AI-augmented sibling of `skel-gen`. It has
  **two modes**:
  - **Full-stack mode** (default when no positional `skel_name`): the
    dialog asks separately for a **backend** skeleton and a
    **frontend** skeleton, then generates both into the same wrapper.
    Defaults: backend = first skel that ships the wrapper-shared
    items API; **frontend = `ts-react-skel`** (since 2026-04). Both
    halves are optional: pass `--no-frontend` for a backend-only
    project, `--no-backend` for a frontend-only one. The dialog
    refuses the "neither" combination. The user supplies one project
    name, two service display names, the canonical item entity, an
    auth style, and **three custom freeform prompts**
    (`backend_extra`, `frontend_extra`, `integration_extra`) — each
    piped into the matching phase via the `{backend_extra}` /
    `{frontend_extra}` / `{integration_extra}` placeholders. After
    generating both halves the driver runs the backend's
    `INTEGRATION_MANIFEST` (now with the frontend visible as a
    sibling) plus the test-and-fix loop. Backends that ship the
    wrapper-shared `/api/items` contract (currently
    `python-django-bolt-skel` and `python-fastapi-skel`) give the
    React frontend a working items round-trip out of the box; for
    other backends the dialog prints a warning. In frontend-only
    mode the React bundle is generated against an external
    `BACKEND_URL` (also warned about).
  - **Single-skeleton mode** (legacy): when an explicit positional
    `skel_name` is given, only that one skeleton is generated.
    Same behavior as pre-2026-04 invocations — kept for scripted
    users.
- **All 10 skeletons are AI-supported** — Python (django, django-bolt,
  fastapi, flask), Java (spring), Rust (actix, axum), Next.js (js),
  React (ts-react), and Flutter (flutter). The full-stack picker
  auto-partitions them via `split_skels_by_kind()` (everything that
  returns `kind=frontend` from the marker-file detector goes into the
  frontend list; the rest are backends — `ts-react-skel` and
  `flutter-skel` are the two frontend kinds today). Run
  `_bin/skel-gen-ai` with no arguments to enter the dialog. The
  older `--auth-details` flag is still accepted as a backwards-compat
  alias for `--backend-extra`.
- `_bin/skel-gen-ai` runs **two Ollama sessions back-to-back** (both now
  routed through the `_bin/skel_rag/` RAG agent — see below):
  1. **Per-target phase** (always) — rewrites the files listed in the
     per-skel `MANIFEST` for the user's `{item_class}`.
  2. **Integration phase** (opt-in via `INTEGRATION_MANIFEST` in the
     same per-skel file) — discovers sibling services in the wrapper,
     embeds their key files into a `{wrapper_snapshot}` prompt
     placeholder (or the new `{retrieved_siblings}` block when the
     manifest opts in), writes integration code + tests, then runs a
     bounded test-and-fix loop (`./test` → ask Ollama to patch failing
     files → re-run, capped at `fix_timeout_m` minutes — default 120). The integration
     phase is currently shipped only for `python-django-bolt-skel`;
     other skels gracefully skip it. Disable with `--no-integrate` /
     `--no-test-fix` when iterating on prompts.
- **AI generation goes through `_bin/skel_rag/`** (since 2026-04). The
  package indexes each skeleton's reference templates with tree-sitter
  + FAISS so prompts retrieve only the most relevant chunks via a local
  embedding model (default `BAAI/bge-small-en-v1.5`). `skel_ai_lib.py`
  is now a thin shim that re-exports every public symbol and delegates
  orchestration to `skel_rag.agent.RagAgent`; the LLM call goes through
  `langchain_ollama.ChatOllama`. The legacy `{template}` /
  `{wrapper_snapshot}` placeholders still work, and manifests can opt
  into `{retrieved_context}` / `{retrieved_siblings}` (FastAPI is the
  reference migration). Install once with `make install-rag-deps`. The
  debug CLI is `_bin/skel-rag` (`index` / `search` / `info` / `clean`).
  Full reference: `_docs/LLM-MAINTENANCE.md` → "`_bin/skel_ai_lib.py`
  (legacy shim) + `_bin/skel_rag/` (RAG agent)".
- **Every backend skel** — Python (`python-django-skel`,
  `python-django-bolt-skel`, `python-fastapi-skel`, `python-flask-skel`),
  Java (`java-spring-skel`), Rust (`rust-actix-skel`, `rust-axum-skel`),
  and Next.js (`next-js-skel`) — reads its database and JWT configuration from the
  wrapper-level `.env` first, then its local `.env`. Per-stack
  conventions:
  - **Python**: `python-dotenv` + a `_build_databases()` /
    `_resolve_database_url()` helper in `settings.py` / `core/config.py`
    / `app/config.py`. JWT material exposed as `settings.JWT_*` (Django)
    or `config.JWT_*` (FastAPI/Flask).
  - **Java**: `application.properties` placeholders
    (`${SPRING_DATASOURCE_URL:${DATABASE_JDBC_URL:...}}`) plus the
    `com.example.skel.config.JwtProperties` bean (registered via
    `@ConfigurationPropertiesScan`).
  - **Rust**: `src/config.rs::Config::from_env()` + `load_dotenv()` (the
    helper walks up to `<wrapper>/.env` before reading the local file).
    `Config` lives inside `AppState` so handlers pull it from
    `web::Data<Arc<AppState>>` (Actix) or `State<Arc<AppState>>` (Axum).
  - **Next.js**: `src/config.js` with the `dotenv` package loading the
    service `.env` first then `<wrapper>/.env`. Exposes a single `config`
    object with `databaseUrl`, `dbPath`, `jwt`, and `service` namespaces.
    Next.js App Router API routes import from `../../lib/db` and
    `../../lib/auth` (relative paths).
  Never hardcode a sqlite path or JWT secret in any skel template; the
  env-driven flow is the contract that lets a token issued by one
  service be accepted by every other service in the same wrapper. The
  wrapper `.env` ships `DATABASE_URL` (Python form), `DATABASE_JDBC_URL`
  / `SPRING_DATASOURCE_URL` (JVM form) side-by-side — keep them in sync
  when switching to Postgres.
- **Frontend skels** read the same wrapper-shared env, just at
  different lifecycle points:
  - **React** (`ts-react-skel`): `vite.config.ts` reads
    `<wrapper>/.env` at *build time* and bakes the safe subset into
    the bundle as `VITE_*` keys; `src/config.ts` re-exports them as
    `config.backendUrl` / `config.jwt.*` / `config.services`.
    `JWT_SECRET` is NOT promoted into the bundle.
  - **Flutter** (`flutter-skel`): the gen script copies
    `<wrapper>/.env` into the project as a bundled asset
    (`pubspec.yaml`'s `flutter.assets`), and `lib/config.dart` reads
    it at *runtime* via `flutter_dotenv`. The JWT bearer token is
    persisted via `flutter_secure_storage` (Keychain on iOS,
    EncryptedSharedPreferences on Android, encrypted localStorage on
    web). `AppConfig` deliberately omits `JWT_SECRET` so it never
    lands in a mobile bundle. State management uses Flutter's
    built-in `ValueNotifier` / `ChangeNotifier` / `InheritedNotifier`
    primitives — no `provider` / `riverpod` / `bloc` dep.
- After generation, `skel-gen` renders the templated `_skels/_common/AGENTS.md`
  (and, when present, the matching `CLAUDE.md`) into the new project so the
  generated tree ships with agent rules wired in.
- `_test_projects/` is the **only** directory where you may create scratch /
  reproduction / debug projects. Never hand-edit anything inside it —
  regenerate with the appropriate `make gen-*`, `_bin/skel-gen`, or
  `_bin/skel-gen-ai` invocation.
- **Skeleton versioning + `./ai upgrade`** (since 2026-04). Every skel
  ships a `VERSION` file (semver) and a `CHANGELOG.md` (Keep-a-Changelog
  format). The pipeline:
  - `install-ai-script` reads `<skel>/VERSION` and writes
    `skeleton_version` into the service sidecar so each generated
    service remembers the template revision it was built from.
  - `_bin/skel-backport apply` bumps `<skel>/VERSION` (semver patch)
    and prepends a `## [VERSION] - DATE` entry to
    `<skel>/CHANGELOG.md` listing every backported file. The
    changelog is the auditable, replayable log of accepted
    service-to-template changes.
  - `./ai upgrade` (per-service) reads the sidecar's
    `skeleton_version`, compares to the skel's current `VERSION`,
    extracts the matching CHANGELOG entries, and synthesises an AI
    request that asks the model to upgrade the service to vY by
    applying those changes. Dispatched through the standard
    propose/apply flow so git stash + fix-loop + verify still
    apply. Dry-run by default; pass `--apply` to commit. On
    success the sidecar's `skeleton_version` is rewritten.
  - **Wrapper-level `./ai` defaults to fan-out** — `./ai
    "REQUEST"` from the project root runs against every service
    by default; `./ai <slug> "REQUEST"` still scopes to one
    service. Same applies to `./ai upgrade` and `./backport`.
  - Smoke runners: `make test-ai-upgrade` (no LLM, no-op +
    outdated paths), `make test-ai-fanout` (no LLM, two-service
    wrapper), `make test-backport-script` (now also verifies
    VERSION bump + CHANGELOG entry).
  - Implementation: `_cmd_upgrade` + `_changelog_excerpt` /
    `_semver_tuple` in `_bin/dev_skel_refactor_runtime.py`,
    `_bump_skeleton_version` + `_bump_patch` in
    `_bin/dev_skel_backport.py`, `FAN_OUT_SCRIPTS` in
    `_skels/_common/common-wrapper.sh`.

---

## 3. Default Maintenance Workflow

Use this workflow whenever the user says "do maintenance" or asks you to
verify the repo. It mirrors `_docs/LLM-MAINTENANCE.md` so Claude does not
need to context-switch:

1. From the repo root, run:
   - `make clean-test`
   - `make test-generators`
2. Investigate every failure and apply minimal, surgical fixes in the
   affected skeletons / scripts. Re-run the same commands until they are
   green.
3. Once tests pass, update the docs and rules files to match the new
   behaviour:
   - Cross-agent: `/AGENTS.md`, `/CLAUDE.md`
   - Global rules: `_docs/JUNIE-RULES.md`, `_docs/LLM-MAINTENANCE.md`
   - Per-skeleton: `_skels/<name>/AGENTS.md`, `_skels/<name>/CLAUDE.md` (if
     present), `_skels/<name>/JUNIE-RULES.md`, and the matching `_docs/<name>.md`
4. If the user explicitly scoped the request to one skeleton, narrow the
   tests and doc updates to that skeleton plus any global rules that must
   change as a side effect.

For long-running maintenance, prefer running `./maintenance` (or the
underlying `make clean-test && make test-generators && ./test`) in the
background and surface only the failures.

---

## 4. Claude Code Operational Notes

These are conventions specific to the way Claude Code interacts with this
repository:

1. **Plan before non-trivial edits.** If a request will touch more than one
   skeleton, change generator UX, or alter dependency policy, draft a Plan
   first and (when appropriate) confirm with the user before executing it.
2. **Track multi-step work with the Task tools.** Anything with more than
   ~3 distinct steps belongs in a task list so the user can follow progress.
   Mark tasks `in_progress` before starting and `completed` immediately after
   finishing — never batch.
3. **Prefer the dedicated tools** (`Read`, `Edit`, `Write`, `Glob`, `Grep`)
   over shelling out via `Bash`. Reach for `Bash` only when no built-in tool
   fits (running `make`, executing scripts, inspecting git state).
4. **Use the Explore subagent** for broad codebase research that would
   otherwise spam the main context. Use `Plan` for design work. Use
   `general-purpose` agents for parallelisable independent investigations.
5. **Confirm before risky actions.** Pushing branches, force-pushing,
   running `git reset --hard`, deleting `_test_projects/` outside of
   `make clean-test`, or modifying `.dev_skel.conf` all require explicit
   user approval.
6. **Memory hygiene.** This project's structure, conventions, and file
   layout are derivable from the repo itself — do not save those into the
   auto-memory system. Only persist genuinely surprising user preferences
   or non-obvious project facts.
7. **Status line and outputs.** Keep textual answers terse. Use code blocks
   for commands and `path:line` for code references.

---

## 5. Editing Conventions for Claude

1. Always `Read` a file before editing or rewriting it.
2. Prefer minimal, surgical diffs that solve the immediate issue. Do not
   refactor unrelated code or add speculative abstractions.
3. Do not modify generator-owned files for ts-react-skel
   (`package.json`, `package-lock.json`, `tsconfig.json`,
   `tsconfig.node.json`, `vite.config.ts`) — they are managed by Vite's
   create command.
4. Do not modify Django generator-owned files (`manage.py`, key
   `myproject/*` files) or Rust skeleton-owned files (`Cargo.toml`,
   `src/main.rs`) — see each skeleton's `merge` script for the exact lists.
5. Never weaken or skip failing tests. Investigate root causes instead.
6. Never commit `node_modules/`, `.venv/`, `target/`, `dist/`, or other
   build artefacts.
7. Update both `/AGENTS.md` and `/CLAUDE.md` when you change cross-agent
   rules, so other LLM harnesses stay in sync.

---

## 6. Working with the Ollama AI Generator

When the user asks Claude to "use Ollama" / "AI-generate a service" / etc:

1. Verify Ollama is running (`curl -sf http://localhost:11434/api/tags`)
   and the requested model is pulled (`ollama list`). The default model
   is `qwen3-coder:30b` and the default `OLLAMA_TIMEOUT` is `1800`
   seconds (30 min — covers the 30-40 s cold-load + multi-minute
   completions a 31B-class model can take on a long file). Drop to a
   smaller model (e.g. `qwen2.5-coder:7b`) on slower hardware via
   `OLLAMA_MODEL=...`.
2. Prefer running `_bin/skel-gen-ai --dry-run --no-input` first to confirm
   the manifest target list, then run the real generation. Real generation
   against a 30B-class instruction model can take **2–10 minutes per
   file**, so do not speculatively re-run it. Use `--skel <name>` to test
   a single skeleton instead of all of them.
3. AI manifests live at `_skels/_common/manifests/<skel>.py`. To extend
   support to a new skeleton, copy an existing manifest and edit the
   `targets` list. Available placeholders are documented in
   `_docs/LLM-MAINTENANCE.md` and at the top of `_bin/skel_ai_lib.py`.
4. Never hand-edit files that an AI manifest is set up to regenerate; if
   the prompt is wrong, fix the manifest and re-run `skel-gen-ai`.
5. The AI generator only rewrites the files listed in the manifest; the
   rest of the project (Dockerfile, Makefile, requirements, etc.) is still
   produced by the static `skel-gen` path. Keep that boundary clear when
   debugging — if a file is missing, check whether it should come from the
   skeleton's `merge` script or from the AI manifest.
6. Use `_bin/skel-test-ai-generators` (or `make test-ai-generators` /
   `make test-gen-ai-<skel>`) to validate the AI pipeline end-to-end after
   editing a manifest. Always run `make test-ai-generators-dry` first
   to confirm dispatch + base scaffolding work before paying for the real
   Ollama time. The runner exits with code `2` (treated as "skipped") when
   Ollama is unreachable, so it is safe to call from longer scripts.
7. **Shared-DB integration test**: `make test-shared-db` (or
   `make test-shared-db-python` for the fast Python-only path) generates
   a wrapper containing every backend skeleton, seeds the shared
   SQLite `items` table, and verifies each backend can read the seed
   row through `DATABASE_URL`. Run this after touching any backend
   skel's settings/config helper or the wrapper-shared env contract —
   it is the cross-language proof that the env-driven flow is sound.
   It auto-skips toolchains (Java/Rust/Node) that aren't installed.
8. **React + django-bolt integration test**: `make test-react-django-bolt`
   generates a wrapper containing both `python-django-bolt-skel` and
   `ts-react-skel`, rewrites `BACKEND_URL` to a non-conflicting port,
   re-builds React (verifies the bundle bakes the right URL), runs
   `makemigrations` + `migrate`, starts the django-bolt server, and
   exercises the full `register → login → create item → list items →
   complete` flow over real HTTP. Run this after any change to the
   django-bolt `app/api.py`, `app/services/auth_service.py`, or the
   React `src/api/items.ts` to confirm the cross-stack contract still
   holds. Skips gracefully when Node/npm is missing. Takes ~3 minutes
   on a cold cache (npm install + pip install dominate the runtime).

## 6.2 Complex AI Generation Test: Pizzeria Orders (FastAPI + Flutter)

Full playbook for generating and testing a complete pizzeria ordering
application (FastAPI backend + Flutter frontend) from AI prompts alone.

**Read:** [`_docs/PIZZERIA-TEST-PLAYBOOK.md`](_docs/PIZZERIA-TEST-PLAYBOOK.md)

Covers: domain model (MenuPosition, Order, OrderPosition, OrderAddress),
14-step HTTP integration flow, AI prompt engineering, scripted
non-interactive generation, 3-tier test matrix, fix-loop decision tree,
and a 9-point definition of done. The test proves `dev_skel` can
generate a domain-specific app automatically with instructions only.

Quick commands:

```bash
make test-pizzeria-orders          # full run (requires Ollama + Flutter)
make test-pizzeria-orders-keep     # same, keep _test_projects/ on disk
_bin/skel-test-pizzeria-orders     # direct script invocation
```

---

## 6.3 Backporting Service Edits Into the Skeleton (`./backport`)

The sibling of `./ai` for the **service → template** direction.
Every generated service ships `./backport` (installed by the same
`common-wrapper.sh` hook that installs `./ai`). Use it after the
user has hand-edited or `./ai`-edited files inside their service
and wants to propagate those changes into the source skeleton so
future generations inherit them.

Workflow:

1. Suggest `./backport` (or `./backport propose`) first — it's a
   dry-run that lists every service file that differs from its
   same-relative skeleton file.
2. Review the list with the user. Each candidate is
   `service_path → skeleton_path`; the underlying CLI writes a JSON
   summary to `<dev_skel>/.ai/backport/<ts>-<sha>/result.json` for
   audit.
3. `./backport apply` writes the changes back into the skeleton
   tree (idempotent: re-running on a clean tree reports "no
   backportable changes found"). The maintainer must commit / push
   the skeleton diff manually.

The script REQUIRES a reachable dev_skel checkout. When run from a
detached service it exits 1 with an actionable error pointing the
user at `$DEV_SKEL_ROOT` or a fresh clone. Auto-detection order
mirrors `./ai`: env var → walk-up → `~/dev_skel` / `~/src/dev_skel`
/ `/opt/dev_skel` / `/usr/local/share/dev_skel`.

Sidecar: `./backport` reads `.skel_context.json` in the service
directory to know which skeleton to write to. The sidecar is
created by `install-ai-script` when `common-wrapper.sh` runs —
each `gen` script exports `SKEL_NAME=<basename of $SKEL_DIR>`
before calling common-wrapper, and only the just-generated service
gets a force-overwrite (sibling services keep their existing
sidecars).

Operator commands:

* `make test-backport-script` — cheap propose+apply round-trip
  smoke (modifies one file, applies, asserts the skel updated,
  reverts via `git checkout`).
* `_bin/skel-backport propose <service>` /
  `_bin/skel-backport apply <service>` — the underlying maintainer
  CLI that `./backport` forwards to.

Implementation:

* `_skels/_common/refactor_runtime/backport` — per-service shim.
* `_bin/dev_skel_backport.py` — maintainer-side propose/apply
  engine. Pure file-diff, no LLM involvement.
* `_bin/skel-backport` — top-level CLI wrapper.
* `_bin/skel-test-backport-script` — smoke harness.

---

## 6.4 Project-wide `./ai` (wrapper-level + cross-call memory)

Two layers turn the per-service `./ai` into a project-wide tool:

**Wrapper-level dispatcher** at `<wrapper>/ai` (auto-generated by
`common-wrapper.sh`). Three modes:

```
./ai "REQUEST"                 # forwards to the FIRST service
./ai <service> "REQUEST"       # forwards to a specific service
./ai --all "REQUEST"           # FAN-OUT — runs against every service
```

`--all` is the cross-service refactor mode: a single request lands
in every backend + frontend in the wrapper. Same flag works for
`./backport --all` (batch backporting from multiple services).

**Cross-call memory** — every `./ai apply` appends one JSONL entry
to BOTH `<service>/.ai/memory.jsonl` AND `<wrapper>/.ai/memory.jsonl`
with the request, edited files, rationale (truncated to 800 chars),
and pass/fail status. The next `./ai propose` (in any service of
the wrapper) prepends the last 5 entries from the wrapper-shared
log to the LLM prompt as a `## PREVIOUS_AI_RUNS` block. The model
sees what was done before and can avoid redoing or undoing prior
work — including work done in OTHER services within the same
wrapper.

`./ai history` prints both layers (project memory across services +
local scratch runs in this service). Wrapper-level `./ai history`
forwards to the first service's history but the project-memory
section is identical regardless of which service runs it.

Operator command: `make test-ai-memory` (no LLM). Implementation:
`_bin/dev_skel_refactor_runtime.py` (`_record_apply_to_memory`,
`_load_project_memory_block`), `_skels/_common/common-wrapper.sh`
(dispatch-script template with `--all` recogniser).

---

## 6.2 Refactoring Inside a Generated Service (`./ai`)

When the user is already cd'd into a generated service and wants AI
help refactoring its code, every Cookiecutter-templated skel ships
`./ai` (plus a vendored `.ai_runtime.py`) — installed automatically
by `_skels/_common/refactor_runtime/install-ai-script` from
`common-wrapper.sh`. Do NOT confuse with `_bin/skel-gen-ai`
(template → service) or `_bin/skel-backport` (service → template);
`./ai` is **service → service** and stays inside the service dir.

Workflow:

1. Confirm the service has `./ai` (it does; landed there at gen time).
2. Suggest `./ai "<one-sentence description>"` as a dry-run first.
   The proposals + RATIONALE land in `.ai/HEAD/`. The `.ai/`
   directory is git-ignored.
3. Review the diff with the user before suggesting `./ai apply "..."`.
4. After `apply`, the script runs the service's test command (read
   from `.skel_context.json` or defaults to `./test`) automatically
   and invokes the fix-loop on failure. Don't re-run tests manually
   unless `./ai` reports a non-zero exit.
5. Other subcommands: `./ai history`, `./ai explain`,
   `./ai verify`, `./ai undo`.

Two activation modes — auto-detected:

* **In-tree** (dev_skel checkout reachable) — full FAISS retrieval
  via `skel_rag.agent.RagAgent`, fix-loop via the shared
  `skel_ai_lib.run_test_and_fix_loop`. Same call stack as
  `skel-gen-ai`.
* **Out-of-tree** (service detached from dev_skel) — stdlib-only
  retrieval (ripgrep with a pathlib fallback) + a bundled minimal
  fix-loop in `.ai_runtime.py`. No third-party imports beyond the
  stdlib + a single `urllib.request` call to Ollama.

Safety contract (cannot be defeated by adversarial LLM output):

* Every write is checked against `service_dir.resolve()` and skipped
  if it lands outside.
* `apply` refuses to run on a dirty git tree without `--allow-dirty`.
* The pre-apply tree is captured to a git stash; on verification
  failure we `git stash pop` to restore.
* A per-service `.ai/.lock` (O_CREAT|O_EXCL) prevents concurrent
  `apply` runs.
* Path traversal (`../`, absolute paths, `.git`, `.ai`, `refactor`,
  `node_modules`, `.venv`) is rejected by both the parser and the
  applier.

Operator commands:

* `make test-ai-script` — cheap dispatch smoke (no Ollama).
* `make sync-ai-runtime` — copy `_bin/dev_skel_refactor_runtime.py`
  into `_skels/_common/refactor_runtime/` after editing the canonical
  runtime so newly-generated services pick up the changes.
* `_bin/skel-ai SERVICE_DIR "REQUEST" [flags]` — drive `./ai` from
  outside a service (useful for batch refactors).

Implementation lives in:

* `_bin/dev_skel_refactor_runtime.py` (canonical source of truth)
* `_skels/_common/refactor_runtime/{ai,dev_skel_refactor_runtime.py,install-ai-script}`
  (vendored copy + installer; kept in sync via `make sync-ai-runtime`)
* Design doc: `SERVICE_REFACTOR_COMMAND.md`

---

## 7. Verification Checklist

Before declaring a task done, verify the relevant subset of:

- [ ] `make test-generators` is green for the affected skeletons.
- [ ] Updated docs / rules accurately reflect the new behaviour.
- [ ] `_test_projects/` contents were regenerated (not hand-edited).
- [ ] No build artefacts staged for commit.
- [ ] Cross-agent rule files (`/AGENTS.md`, `/CLAUDE.md`,
      `_docs/JUNIE-RULES.md`) agree with each other.
- [ ] Any new or renamed Python helpers in `_bin/dev_skel_lib.py` or
      `_bin/skel_ai_lib.py` are consumed correctly by the CLIs and
      manifests that depend on them.
- [ ] AI manifests still load (`python3 -c "import sys;
      sys.path.insert(0, '_bin'); import skel_ai_lib;
      skel_ai_lib.load_manifest(__import__('pathlib').Path('.'),
      'python-django-skel')"`) and prompts render with a sample context.
- [ ] When you change a manifest or the AI library, run
      `make test-ai-generators-dry` (always cheap) and, if Ollama is
      available, `make test-ai-generators` (slow, ~30+ min total).
- [ ] After pushing, check CI status with `make ci-status` or
      `make ci-watch` (requires `gh auth login` once).
