# Dev Skel — TODO

Concrete, actionable follow-ups. This file complements
[`ROADMAP.md`](ROADMAP.md): the roadmap is the long-term vision; this
list captures **specific tasks still open** plus bridge items that turn
the roadmap phases into shippable PRs.

---

## Recently completed (2026-04)

Kept here briefly so the "still open" items make sense.

- **Unified data schema** — all 10 backends now ship `/api/items` +
  `/api/categories` + `/api/auth` + `/api/state`. Data model:
  `user -< item >- category` (nullable FK, SET_NULL) + `user -< state`.
  Both frontends (React + Flutter) ship typed clients for all four
  endpoint families.
- **Cross-stack test extended** — `exercise_items_api` now runs 23+
  HTTP steps: 9 items + 5 categories CRUD + 4 items↔categories FK +
  5 state save/load/delete + anonymous/invalid-token rejection.
  `make test-react-cross-stack` 9/9 green,
  `make test-flutter-cross-stack` 2/2 green.
- **next-js-skel** — js-skel rewritten to Next.js 15 App Router.
  `make test-react-nextjs` passes full pipeline.
- **Dockerfiles + devcontainers** — all 12 skeletons ship multi-stage
  Dockerfile + .devcontainer/ + .dockerignore.
- **`./ai upgrade`** + **wrapper `./ai` fan-out** + **`./backport`
  VERSION/CHANGELOG** — all shipped and tested.
- **CI pipeline** — `make ci-status`/`ci-watch`/`ci-log` via `gh`.
  FastAPI `requirements.txt` CI fix (auto-generate from pyproject.toml).
- **Skeleton Design Guide** — `_docs/SKELETON-DESIGN-GUIDE.md`.
- **Documentation rewrite** — README.md, all `_docs/*.md` files.
- **Full-stack dialog** — frontend defaults to `ts-react-skel`, both
  halves optional.
- **INTEGRATION_MANIFEST for all 10 skels** — every AI-supported
  skeleton now ships integration targets (sibling clients +
  integration tests). `make test-ai-generators-dry` 10/10 green.

---

## ~~Section 1 — INTEGRATION_MANIFEST rollout~~ (DONE)

**Shipped 2026-04.** All 10 AI-supported skeletons now ship an
`INTEGRATION_MANIFEST`. `make test-ai-generators-dry` passes 10/10.

### 1.2 Prompt hardening for non-Python manifests (ongoing)

**Status (2026-04-18).** With `qwen3-coder:30b`, `make test-ai-generators`
results:
- **5/10 pass consistently:** python-django-bolt, python-django,
  python-fastapi, python-flask, next-js.
- **5/10 fail non-deterministically:** flutter, java-spring,
  rust-actix, rust-axum, ts-react. Each failure is the AI generating
  code that doesn't match the skel's exact type signatures (wrong
  constructor arity, missing props, JPA instead of JDBC, module
  import mismatches).

**Root cause.** The 30B-class models don't reliably follow complex
structural constraints in Rust/Java/Flutter/TypeScript. Python and
Next.js succeed because their skels have simpler interfaces.

**Next steps:**
1. Add `--max-retries 1` to the test runner (Section 2.1) so transient
   model errors get a second chance.
2. Include complete working code examples inline in each failing
   manifest's prompt (not just description — literal compilable code
   blocks showing the exact record shape, function signature, or
   component interface the AI must produce).
3. Consider using the 70B model (`deepseek-r1:70b`) for Rust/Java
   manifests if the 30B model can't be hardened enough.

**Acceptance.** `make test-ai-generators` passes 8/10+ consistently.

---

## Section 2 — AI pipeline improvements

### 2.1 Auto-retry on `py_compile` failure

**Why.** Ollama drops parens non-deterministically. Add
`--max-retries N` to `skel-test-ai-generators`.

### 2.2 Multi-file AI phases (entity-driven generation)

**Why.** Each manifest target is rendered in isolation. A phase model
(entity → schemas → routes → tests) where each phase sees earlier
outputs as context would reduce mismatches.

### 2.3 Structured critique loop

**Why.** Ollama sometimes uses wrong constants. A second "critique"
prompt that checks constraints can catch these.

---

## Section 3 — CI/CD & testing

### 3.1 Wire `test-shared-db` into `./maintenance`

**Why.** `make test-shared-db` proves the cross-language env contract
but nothing in CI runs it.

**Scenario.** Append `make test-shared-db-python` to `./maintenance`
(fast, ~25 s).

### 3.2 Postgres mode for `test-shared-db`

**Why.** The test only handles `sqlite:///` URLs. Add `--db postgres`
mode using the wrapper Docker Compose.

### 3.3 Per-runtime ORM exercise for Java / Rust / Go / Next.js

**Why.** Non-Python verifiers use the test runner's own `sqlite3`
instead of each runtime's driver. Ship a `verify-shared-db` script
per skel.

### 3.4 Add go-skel and fastapi-rag-skel AI manifests

**Why.** These 2 skeletons lack AI manifests, so `skel-gen-ai` can't
rewrite their core files for a custom entity.

---

## Section 4 — Docker & orchestration

### 4.1 Per-service entries in wrapper `docker-compose.yml`

**Why.** Only Postgres is declared. Add one container per service so
`docker compose up` boots the whole stack.

### 4.2 `./run dev-all` multi-service launcher

**Scenario.** Spawn each service's `run-dev` in the background, tail
combined logs, `./stop dev-all` to tear down.

### 4.3 Optional reverse-proxy gateway

**Scenario.** New `gateway-traefik-skel` reading
`_shared/service-urls.env` for dynamic routing config.

---

## Section 5 — Project metadata (Roadmap Phase 2)

### 5.1 `dev_skel.project.yml`

**Scenario.** After every gen, `common-wrapper.sh` rewrites
`dev_skel.project.yml` from discovered services. Unblocks Phases 3–6.

### 5.2 `./services info <id>` / `set-active <id>`

**Scenario.** Subcommands reading `dev_skel.project.yml`.

---

## Section 6 — Contracts & observability (Roadmap Phases 3–4)

### 6.1 OpenAPI export per backend

### 6.2 Type-safe codegen (`./contracts gen`)

### 6.3 Structured JSON logging defaults

### 6.4 OpenTelemetry tracing

---

## Section 7 — Documentation polish

### 7.1 Migration guide: legacy `backend-1/` → service-name dirs

### 7.2 Wrapper README "Cookbook" section

### 7.3 Shared database conventions doc

**Files.** New `_docs/SHARED-DATABASE-CONVENTIONS.md` documenting the
canonical `users` + `categories` + `items` + `react_state` schema,
column types per ORM, and the FK/unique constraints every backend
must obey.

---

## Suggested execution order

1. ~~**Section 1** — INTEGRATION_MANIFEST rollout.~~ (DONE)
2. **Section 1.2** — Rust prompt hardening (quick win).
3. **Section 3.1** — wire shared-DB test into CI.
4. **Section 3.4** — AI manifests for go-skel + fastapi-rag-skel.
5. **Section 2.1** — auto-retry on AI failures.
6. **Section 4.1** — per-service docker-compose entries.
7. **Section 5** — project metadata (unblocks Phases 3–6).
8. **Section 6** — contracts + observability.
9. **Section 7** — docs polish (can land any time).

When closing an item, prefer adding a one-line "**Done**" note under
the acceptance check rather than deleting the entry.
