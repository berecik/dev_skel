# Dev Skel — TODO

Concrete, actionable follow-ups for the dev_skel repo. This file complements
[`ROADMAP.md`](ROADMAP.md): the roadmap is the long-term vision; this list
captures **specific tasks that are still open after the most recent
shared-environment + integration-test work**, plus the bridge items that
turn the roadmap phases into shippable PRs.

Each item includes the **why**, the **files** to touch, a step-by-step
**scenario** for realising it, and the **acceptance check** you can run
to verify it works. Items are ordered roughly by priority — the early
sections are small follow-ups that should land before the bigger
roadmap-driven work.

---

## Section 1 · Hardening & verification (small follow-ups)

These are quick wins from the recent shared-env / integration-test work.
Most are < 1 hour each.

### 1.1 Verify the hardened django manifest prompt with one live AI run

**Why.** The `python-django-skel` `settings.py` prompt was hardened with a
literal code block + paren-balance reminder after a single Ollama run
dropped a closing paren on `load_dotenv(...)`. The fix is shipped but not
re-verified live.

**Files.** `_skels/_common/manifests/python-django-skel.py:60-95`.

**Scenario.**
1. Make sure `ollama serve` is running and the default model
   (`gemma4:31b`) is pulled — or override via `OLLAMA_MODEL=...`.
2. Run `make test-gen-ai-django` once.
3. If it fails on `settings.py` again, inspect `_test_projects/test-ai-python-django/sample_service/myproject/settings.py` and add another concrete code-block constraint to the prompt.
4. Repeat 1–3 until 3 consecutive runs pass.

**Acceptance.** `make test-gen-ai-django` passes 3× in a row without
syntax errors. The Django app starts cleanly via `manage.py check`.

---

### 1.2 Auto-retry on `py_compile` failure inside `_bin/skel-test-ai-generators`

**Why.** Ollama output is non-deterministic. A single dropped paren shouldn't
fail the whole pipeline — retrying the same target once is cheap and
hides ~80% of one-off model hiccups.

**Files.** `_bin/skel-test-ai-generators` (the `_validate_django` /
`_validate_django_bolt` / `_validate_fastapi` / `_validate_flask`
helpers and `generate_targets` callsite).

**Scenario.**
1. Add a `--max-retries N` flag to `_bin/skel-test-ai-generators` (default `1`).
2. After `generate_targets` returns, run the syntax check (`py_compile`)
   on every written file.
3. For each file that fails: re-run `client.chat()` for that single
   target (re-using the same prompt + reference) up to `N` times.
4. After each retry, re-run the syntax check.
5. Surface "retried N×" in the per-target line of the summary so users
   can see when retries kicked in.

**Acceptance.** Force a deliberate model glitch (e.g. point at a tiny
quantised model that drops parens often) and confirm `--max-retries 2`
recovers cleanly while `--max-retries 0` fails fast.

---

### 1.3 Vite template regression watchdog for `ts-react-skel`

**Why.** Vite 8 unexpectedly regressed `npm create vite@latest --template
react-swc-ts` to a vanilla-TS scaffold (no `react`, no `react-dom`, no
`@vitejs/plugin-react-swc`, no `index.html` with `#root`). The skeleton
now ships its own `tsconfig.json`, `index.html`, `src/main.tsx` and
explicitly installs the missing packages — but if the upstream template
changes shape again the skel can silently break.

**Files.** `_skels/ts-react-skel/test_skel`,
`_skels/ts-react-skel/gen:181-200`, `_skels/ts-react-skel/merge`.

**Scenario.**
1. After the `npm create vite` step in `gen`, parse the generated
   `package.json` and assert `react`, `react-dom`, and
   `@vitejs/plugin-react-swc` are present (or install them if missing —
   which we already do).
2. Add a `test_skel` post-step that greps the built `dist/assets/*.js`
   for the wrapper-shared values (`devskel`, `HS256`, `API base`) — if
   they are missing, fail with a clear "Vite env baking broke" message.
3. Document the upstream regression in
   `_skels/ts-react-skel/CLAUDE.md` so future Claude / Junie sessions
   know to check the template shape on bumps.

**Acceptance.** `make test-gen-react` fails loudly with an actionable
error if any of the React entry-point files vanish from the upstream
template; it currently passes with a 192 KB bundle containing
`devskel` / `HS256` / `API base`.

---

## Section 2 · Recently deferred items (called out as "out of scope")

### 2.1 Postgres support in `_bin/skel-test-shared-db`

**Why.** The shared-DB integration test currently only handles
`sqlite:///` URLs. To exercise the Docker Compose Postgres path that
ships in every wrapper, the runner needs a `postgresql://` mode.

**Files.** `_bin/skel-test-shared-db` (`seed_items_table`, `verify_python_backend`,
`verify_runtime_smoke`, `VERIFY_SCRIPT`, `WRITE_SCRIPT`).

**Scenario.**
1. Add a `--db <sqlite|postgres|auto>` flag to `_bin/skel-test-shared-db`
   (default `auto`: pick `postgres` when `DATABASE_URL` in the wrapper
   `.env` starts with `postgres`).
2. When `postgres` is selected:
   - Detect Docker via `shutil.which("docker")`. If absent, exit with
     code `2` (toolchain skip) and a friendly message.
   - Run `docker compose up postgres -d` from the wrapper directory and
     wait for the healthcheck (loop on `pg_isready` for ~30 seconds).
   - Switch the seed function to use `psycopg2` or stdlib's bundled
     postgres driver (use `pg8000` to stay dependency-free).
   - Each verifier runs the same SELECT but via `pg8000` instead of
     `sqlite3`.
3. After the test finishes, tear down with `docker compose down`
   (unless `--keep`).
4. Add a `--db postgres` `make test-shared-db-postgres` Makefile target.

**Acceptance.**
```bash
docker compose --version  # required
make test-shared-db-postgres  # runs every Python backend against the same postgres
```
All Python backends report `seed row visible`, the cross-stack
write/read round-trip succeeds, and the postgres container is cleaned
up on success.

---

### 2.2 Per-runtime ORM exercise for Java / Rust / JS in `test-shared-db`

**Why.** Java / Rust / Node verifiers in `test-shared-db` currently use
the test runner's own stdlib `sqlite3` to confirm the seed row is
visible. That proves the file paths are aligned but does NOT exercise
each runtime's actual DB driver. A more authentic test compiles a tiny
verify binary per stack.

**Files.** `_bin/skel-test-shared-db` (`verify_runtime_smoke`),
`_skels/java-spring-skel/`, `_skels/rust-actix-skel/`,
`_skels/rust-axum-skel/`, `_skels/js-skel/`.

**Scenario.**
1. **Java (Spring Boot)**: ship a tiny `VerifyDb.java` main class in
   the skel that uses `java.sql.DriverManager` to open
   `${SPRING_DATASOURCE_URL}` and SELECT from `items`. Add a
   `verify-shared-db` script that runs `mvn -q exec:java
   -Dexec.mainClass=com.example.skel.VerifyDb -Dexec.args="${SEED_NAME}"`.
   Cache the Maven `.m2` directory between runs to keep startup time
   under ~5 s.
2. **Rust (Actix / Axum)**: add a `verify_db.rs` example
   (`examples/verify_db.rs`) that pulls in `rusqlite` (or `sqlx` if
   `DATABASE_URL` is postgres) and runs the SELECT. Run via `cargo run
   --example verify_db -- "${SEED_NAME}"`. First run is slow
   (compilation), but the runner can cache `target/` between
   invocations.
3. **JS**: use Node 22's native `node:sqlite` module (no extra
   dependency). Ship `src/verify-shared-db.js` and a wrapper
   `verify-shared-db` script that calls `node src/verify-shared-db.js
   "${SEED_NAME}"`.
4. Update `_bin/skel-test-shared-db` to call each backend's
   `verify-shared-db` script via `subprocess.run` and report the result.
5. Add a `--smoke-only` flag that keeps the current behaviour (skip the
   per-runtime exercise) for fast CI runs.

**Acceptance.**
```bash
make test-shared-db
# every backend now runs its own runtime; total runtime stays under
# ~3 minutes on a warm cache. JVM/Rust/Node failures show stack-native
# errors (e.g. JDBC URL parse error) so users can debug them.
```

---

### 2.3 Wire `test-shared-db` into the maintenance script + CI

**Why.** `make test-shared-db` is the only test that proves the
cross-language env contract holds. Right now it's manual; nothing in
`maintenance` or the GitHub Actions workflow runs it.

**Files.** `maintenance` (root script), `.github/workflows/maintenance.yml`.

**Scenario.**
1. Append `make test-shared-db-python` to the `maintenance` script
   (the python-only path is fast — ~25 s — and doesn't need Docker /
   JDK / Rust / Node).
2. Add a separate `.github/workflows/shared-db.yml` that runs the full
   `make test-shared-db` against a matrix of `{python, python+jvm,
   python+rust, python+node, all}` stacks. Use the GitHub Actions
   `setup-java`, `setup-rust`, `setup-node` actions to install
   toolchains on demand.
3. Document the new workflow in `_docs/LLM-MAINTENANCE.md` so future
   Claude sessions know which tests are CI-blocking.

**Acceptance.**
- `./maintenance` includes a "Verifying shared DB across Python
  backends..." section that fails fast on regression.
- The `shared-db.yml` workflow runs on every push to `master` and PR
  against `master`, with each matrix cell taking < 5 minutes.

---

### 2.4 Per-service entries in the wrapper `docker-compose.yml`

**Why.** The wrapper currently ships a `docker-compose.yml` with only
the Postgres backing service plus a single commented-out
`ticket_service:` example. Real multi-service projects need one
container per service so `docker compose up` boots the whole stack.

**Files.** `_skels/_common/common-wrapper.sh` (the docker-compose
generation block at line ~165).

**Scenario.**
1. After every wrapper-script regeneration, walk
   `<wrapper>/<service>/install-deps` files (the same discovery
   `./services` uses).
2. For each service, render a compose entry with:
   - `image: ${COMPOSE_PROJECT_NAME:-devskel}-<slug>:dev` (or
     `build: ./<slug>`).
   - `env_file: .env` and the auto-generated
     `_shared/service-urls.env`.
   - `depends_on.postgres.condition: service_healthy` (the existing
     compose Postgres has a `pg_isready` healthcheck).
   - `ports: - "${SERVICE_PORT_<UPPER_SLUG>}:${SERVICE_PORT_<UPPER_SLUG>}"`
     (using the auto-allocated port from `service-urls.env`).
3. Re-run the test runner — confirm `docker compose config` parses the
   generated file and `docker compose up` brings every service up
   against the same postgres container.
4. Detect previously customised entries (look for a `# user-edit:`
   marker) and preserve them across re-generations so user tweaks are
   never overwritten.

**Acceptance.**
```bash
make gen-django-bolt NAME=myproj SERVICE='Ticket Service'
make gen-fastapi     NAME=myproj SERVICE='Auth API'
cd myproj
docker compose config       # parses cleanly
docker compose up -d
docker compose ps           # shows postgres + ticket_service + auth_api
```

---

## Section 3 · AI generator coverage

### 3.1 ~~AI manifest for `ts-react-skel`~~ (LANDED — see note)

**Status.** Shipped. `_skels/_common/manifests/ts-react-skel.py`
rewrites the canonical `Item`-shaped layer (`src/api/items.ts`,
`src/hooks/use-items.ts`, `src/components/ItemList.tsx` /
`ItemForm.tsx`, and `src/App.tsx`) for the user's `{item_class}`
while preserving the wrapper-shared JWT auth layer
(`src/auth/`) and the React state-management layer
(`src/state/`) verbatim. The system prompt references
`config.backendUrl` (resolved by the Vite plugin from `BACKEND_URL`
in the wrapper `.env`), tells Ollama to keep the
`<AppStateProvider>` wrapper in `App.tsx`, and explicitly forbids
referencing `config.jwt.secret`.

**Remaining nice-to-have.** A `_validate_react` helper inside
`_bin/skel-test-ai-generators` that runs `npm run build` against the
generated frontend and asserts the bundle contains the new
component names via `strings dist/assets/*.js | grep
<item_class>`. Today the AI dry-run validates the manifest renders
but does not run a live build — adding the validator would catch
JSX regressions from prompt drift.

**Acceptance.** `make test-gen-ai-react` produces a frontend that
builds cleanly and renders the new entity. The shared-DB test
ignores the frontend (it's not a backend) but the AI test runner
passes.

---

### 3.1a Roll out `INTEGRATION_MANIFEST` to the other 8 skels

**Why.** The two-phase Ollama generation (per-target + integration +
test-and-fix loop) shipped in `_bin/skel_ai_lib.py` and the
`python-django-bolt-skel` manifest. Only that one skel currently
declares an `INTEGRATION_MANIFEST`; the others gracefully skip the
integration phase. Filling out the remaining 8 manifests gives every
skel a "wire me into the wrapper" pass.

**Files.** One section added to each of these manifest files:
- `_skels/_common/manifests/python-django-skel.py`
- `_skels/_common/manifests/python-fastapi-skel.py`
- `_skels/_common/manifests/python-flask-skel.py`
- `_skels/_common/manifests/java-spring-skel.py`
- `_skels/_common/manifests/rust-actix-skel.py`
- `_skels/_common/manifests/rust-axum-skel.py`
- `_skels/_common/manifests/js-skel.py`
- `_skels/_common/manifests/ts-react-skel.py`

**Scenario per stack.** Copy the django-bolt template (3 targets:
package marker, `sibling_clients`, integration tests) and adapt:

- **python-django** / **python-fastapi** / **python-flask**: same
  Python `urllib.request`-based sibling clients, pytest integration
  tests, `test_command="./test ..."`. The django/fastapi prompts
  must use the per-skel app layout (`api/v1/...` vs
  `app/{service_slug}/`).
- **java-spring**: integration test as a `@SpringBootTest`. Sibling
  clients via `RestTemplate` reading from
  `${SERVICE_URL_<UPPER_SLUG>}` env vars. `test_command="./test"`
  delegates to `mvn test`.
- **rust-actix / rust-axum**: integration test as a `#[actix_rt::test]`
  / `#[tokio::test]` in `tests/integration.rs`. Sibling clients use
  `reqwest` (or `ureq` to stay dependency-light). `test_command="./test"`
  → `cargo test --test integration`.
- **js-skel**: integration tests using `node:test`. Sibling clients
  use the global `fetch`. `test_command="./test"` → `node --test src/`.
- **ts-react-skel**: integration tests using vitest. Mock the sibling
  endpoints with `vi.fn()` for unit-level coverage; add a separate
  `e2e/integration.spec.ts` that hits a running backend if available
  (skip when not). `test_command="npm test -- --run"`.

**Acceptance.**
```bash
make test-ai-generators-dry
# All 9 manifests' integration sections render cleanly.
make test-ai-generators
# Live runs produce a working integration test suite per skel.
```

---

### 3.2 ~~AI manifests for Java / Rust / JS backends~~ (LANDED — needs prompt hardening)

**Status.** AI manifests for `java-spring-skel`, `rust-actix-skel`,
`rust-axum-skel`, `js-skel`, and `ts-react-skel` shipped — **all 9
skeletons are now AI-supported**. Validators (`mvn package`,
`cargo check`, `node --check`, `tsc --noEmit`) are wired into
`_bin/skel-test-ai-generators` and gracefully skip toolchains that aren't
installed. Live runs reveal that the new manifests need a
concrete-example pass to harden the prompts (Ollama produces
syntactically valid code that doesn't always match the framework
APIs); the dry-run path is fully green.

**Remaining work — Rust prompt hardening.** Live cargo checks failed
on a first attempt because the AI's actix-web handler signatures
mismatched the macro expectations (`Path<i64>` extractor, `web::Json`
shape, etc.). Tighten the `rust-actix-skel.py` and `rust-axum-skel.py`
prompts by including a complete working handler skeleton inline so
the model has less to invent. Same pattern as the django settings.py
hardening (paragraph 1.1).

**Original notes.** Currently only the 4 Python backends are AI-supported. The
shared-env wiring is in place for Java, Rust, and JS — adding manifests
is the obvious next step.

**Files.** Three new files:
- `_skels/_common/manifests/java-spring-skel.py`
- `_skels/_common/manifests/rust-actix-skel.py` (and `rust-axum-skel.py`)
- `_skels/_common/manifests/js-skel.py`

**Scenario per stack.**

**Java Spring** (4–6 targets):
- `src/main/java/com/example/skel/model/{ItemClass}.java` — JPA entity.
- `src/main/java/com/example/skel/repository/{ItemClass}Repository.java`.
- `src/main/java/com/example/skel/service/{ItemClass}Service.java`.
- `src/main/java/com/example/skel/controller/{ItemClass}Controller.java`.
- `src/test/java/com/example/skel/controller/{ItemClass}ControllerTest.java`.

The system prompt mentions the wrapper-shared `JwtProperties` bean
already on the classpath and tells Ollama to inject it for token
validation. Validator boots `mvn -q -DskipTests package` and asserts the
JAR builds.

**Rust Actix / Axum** (4–6 targets):
- `src/handlers/{item_name}.rs` — HTTP handlers.
- `src/models/{item_name}.rs` — `serde::Deserialize/Serialize` struct.
- `src/db/{item_name}.rs` — `rusqlite` / `sqlx` queries.
- `tests/{item_name}_handlers.rs` — integration test.

System prompt tells Ollama that `Config` is in `src/config.rs` and is
already wired into `AppState`; handlers should pull it from
`web::Data<Arc<AppState>>` (Actix) or `State<Arc<AppState>>` (Axum).
Validator runs `cargo check` (fast) instead of `cargo build --release`.

**JS (Node)** (3–4 targets):
- `src/handlers/{item_name}.js` — Express-style handlers.
- `src/db/{item_name}.js` — `node:sqlite` queries.
- `src/{item_name}.test.js` — `node --test` tests.

System prompt mentions `import { config } from './config.js'` and
`config.databaseUrl` / `config.jwt.secret`. Validator runs `node --test
src/`.

**Acceptance.**
```bash
make test-ai-generators-dry  # all 7-8 manifests resolve
make test-ai-generators       # all 7-8 generate cleanly against ollama
```

---

### 3.3 Multi-file AI passes (entity-driven generation)

**Why.** Today each manifest target is rendered in isolation. When you
add a new field to the entity, you have to rerun the whole skel and
hope every file lines up. A "phase" model (entity → schemas → routes →
tests → docs) would let the AI re-use earlier outputs as context for
later ones.

**Files.** `_bin/skel_ai_lib.py` (new `Phase` dataclass + multi-pass
runner), all four python AI manifests.

**Scenario.**
1. Extend `AiManifest` with an optional `phases: List[Phase]` field.
   Each phase has a name, a list of target indices, and a flag for
   whether it should re-include earlier phases' outputs as context.
2. When a manifest declares phases, the runner:
   - Renders each phase in order.
   - For phase N+1, the prompt's `{template}` slot is augmented with
     the cleaned outputs of every earlier phase.
3. Migrate `python-django-skel` to use phases:
   - Phase 1: `models.py`.
   - Phase 2: `schemas.py` (with phase 1 output in context).
   - Phase 3: `views.py` + `urls.py` (with phases 1+2 in context).
   - Phase 4: `tests.py` (with phases 1–3 in context).
4. Compare success rate: same model, same prompts, with vs without
   phases. Expect fewer schema/model mismatches.

**Acceptance.** Run `make test-gen-ai-django` 5× before and 5× after
the change; phased version should have ≥ 80% success rate on a
deliberately ambiguous prompt (e.g. `--item-name 'event with start_at
and end_at'`).

---

### 3.4 AI generator: structured rejection & critique loop

**Why.** Sometimes Ollama produces code that compiles but uses the wrong
constants (e.g. `settings.SECRET_KEY` instead of `settings.JWT_SECRET`).
A second LLM pass that critiques the output against the system prompt
could catch these.

**Files.** `_bin/skel_ai_lib.py` (`generate_targets` → add a `critique`
hook).

**Scenario.**
1. After `generate_targets` writes a file, run a tiny "critique" prompt
   that asks the same model: *"Does the following file violate any of
   these constraints? <list the system prompt's CRITICAL bullets>
   Reply with PASS or FAIL and a one-line reason."*.
2. If the critique returns FAIL, retry the original generation with
   the critique reason appended to the prompt as additional context.
3. Cap critiques at 1 per file to bound runtime.

**Acceptance.** Manually plant a violation (e.g. inject
`settings.SECRET_KEY` into the django reference template). Re-run AI
generation; the critique loop should catch and rewrite it.

---

## Section 4 · Multi-service orchestration (Roadmap Phase 1 + 3 + 4 bridge)

### 4.1 `dev_skel.project.yml` metadata file

**Why.** Roadmap Phase 1.1 — wrappers should have a first-class notion
of services beyond "directory exists with an install-deps script". A
metadata file unblocks Phases 2-7.

**Files.** New `_skels/_common/project-yml.sh` helper or extend
`common-wrapper.sh`. Also `_bin/skel-gen` and `_bin/skel-gen-ai` to
update the file on each generation.

**Scenario.**
1. Decide on the schema (YAML, ~20 lines per service):
   ```yaml
   project:
     name: myproj
     created_at: 2026-04-07
   services:
     - id: ticket_service
       kind: backend
       tech: python-django-bolt
       role: main-api
       ports:
         http: 8000
       directory: ./ticket_service
   ```
2. After every `gen`-script invocation, `common-wrapper.sh` rewrites
   `dev_skel.project.yml` from scratch by walking discovered services
   (the same discovery `./services` uses) and merging with the previous
   file's `role` / `ports` / freeform fields.
3. Stable IDs come from the slug; `kind` and `tech` are derived from
   the skeleton name via a hard-coded map in `common-wrapper.sh`.
4. Use stdlib YAML in Python helpers (or a tiny pure-shell emitter);
   no PyYAML dependency in the wrapper.

**Acceptance.**
```bash
make gen-django-bolt NAME=myproj SERVICE='Ticket Service'
cat myproj/dev_skel.project.yml
# project: { name: myproj, ... }
# services: [{ id: ticket_service, kind: backend, tech: python-django-bolt, ... }]
```

---

### 4.2 `./services info <id>` and `./services set-active <id>`

**Why.** Roadmap Phase 1.2. Today `./services` only lists names. Once
metadata exists (4.1), the wrapper can expose richer commands.

**Files.** `_skels/_common/common-wrapper.sh` (the `services` script
generation block).

**Scenario.**
1. Replace the simple `./services` listing with a small subcommand
   parser:
   - `./services list` (default) — current behaviour.
   - `./services info <id>` — pretty-prints the entry from
     `dev_skel.project.yml`.
   - `./services set-active <id>` — writes the chosen id to
     `_shared/active-service` (a tiny single-line file).
2. Update single-shot dispatch wrappers (`./run`, `./lint`, `./format`,
   `./deps`) to read `_shared/active-service` first and fall back to
   "first service in the wrapper" when it's missing.
3. Document the active-service mechanism in the wrapper README.

**Acceptance.**
```bash
./services list                  # ticket_service, auth_api
./services info ticket_service   # tech: python-django-bolt, port: 8000
./services set-active auth_api
./run                            # delegates to auth_api/run, not ticket_service/run
```

---

### 4.3 `./run dev-all` multi-service launcher

**Why.** Roadmap Phase 3.4. Right now `./run` runs one service. To
develop a multi-service project locally you have to open multiple
terminals manually.

**Files.** `_skels/_common/common-wrapper.sh` (new `run-dev-all`
generation block).

**Scenario.**
1. Generate a `run-dev-all` script in the wrapper that:
   - Sources `.env` and `_shared/service-urls.env`.
   - For each service in `dev_skel.project.yml`, spawns
     `<service>/run-dev` in the background, redirecting logs to
     `_shared/logs/<slug>.log`.
   - Records each PID in `_shared/run-dev-all.pids`.
   - Tails all log files in parallel via `tail -F`.
2. Generate a matching `stop-dev-all` script that reads
   `_shared/run-dev-all.pids` and `kill -TERM`s each one.
3. Optionally use `tmux` if it's available for a nicer multi-pane UX —
   detect via `command -v tmux`.

**Acceptance.**
```bash
./run dev-all
# Postgres + ticket_service + auth_api + web_ui all running
# Combined logs streaming to terminal
# Ctrl-C stops everything cleanly
```

---

### 4.4 Optional reverse-proxy gateway service

**Why.** Roadmap Phase 3.3. With multiple services on different ports,
a Traefik or Nginx gateway gives a stable single URL to test against
(`http://localhost:8080/api/...`).

**Files.** New `_skels/gateway-traefik-skel/` skeleton.

**Scenario.**
1. Build a tiny new skeleton: just a `traefik.yml`, a `dynamic.yml`
   generated from `_shared/service-urls.env`, a Dockerfile that runs
   Traefik against the dynamic config, and a `gen` script that takes
   the standard `<wrapper>` argument.
2. Re-runs of `gen-traefik` regenerate `dynamic.yml` from the current
   service URL map so adding/removing services Just Works.
3. Add `gen-traefik` to the root Makefile and document it in README's
   "Common Workflows".

**Acceptance.**
```bash
make gen-traefik NAME=myproj
docker compose up traefik -d
curl http://localhost:8080/api/tickets/  # routed to ticket_service
curl http://localhost:8080/api/auth/login  # routed to auth_api
```

---

## Section 5 · Cross-service contracts (Roadmap Phase 2)

### 5.1 OpenAPI export per backend skeleton

**Why.** Roadmap Phase 2.2. Once contracts exist in a single source of
truth, every consumer (frontends, other backends, mobile) can stay in
sync.

**Files.** `_skels/python-fastapi-skel/`, `_skels/python-django-skel/`,
`_skels/python-django-bolt-skel/`, `_skels/java-spring-skel/`,
`_skels/rust-actix-skel/`, `_skels/rust-axum-skel/`. New
`./contracts export` script per skeleton.

**Scenario.** Per stack:
- **FastAPI**: built-in `app.openapi()` → write to
  `<wrapper>/contracts/openapi/<service-slug>.yaml`.
- **Django (DRF-free)**: use `drf-spectacular`-style introspection or
  ship an `./openapi-export` script that builds the spec by scanning
  the URL conf. Or pull the OpenAPI module out of `django-bolt` for
  Django-Bolt.
- **Django-Bolt**: leverage the built-in `BoltAPI.openapi()` (django-bolt
  ships an OpenAPI generator).
- **Spring Boot**: add `springdoc-openapi` dependency and a Maven goal
  that writes `target/openapi.yaml`, copy to wrapper.
- **Rust Actix / Axum**: integrate `utoipa` and a small `cargo run
  --bin export-openapi` binary.

**Acceptance.**
```bash
./contracts export   # fan-out script generated by common-wrapper.sh
ls contracts/openapi/
# auth_api.yaml  ticket_service.yaml  java_service.yaml
```

---

### 5.2 Type-safe codegen (`./contracts gen`)

**Why.** Roadmap Phase 2.3. Once specs exist, generate typed clients
for every consumer language.

**Files.** New `_bin/contracts-codegen` Python script + per-skel
`./contracts gen` integration.

**Scenario.**
1. Pick `openapi-generator-cli` or `oapi-codegen` (Go) as the engine —
   `openapi-generator-cli` covers more languages.
2. `_bin/contracts-codegen` reads `dev_skel.project.yml`, walks every
   spec in `contracts/openapi/`, and runs the generator per consumer:
   - Pydantic models + `httpx` client → `<service>/shared/contracts/`
     for Python services.
   - TypeScript fetch client → `<frontend>/src/shared/contracts/`.
   - Rust client → `<service>/src/contracts/`.
3. Add a `dev_skel.project.yml` `consumes:` field per service so the
   tool knows which specs to wire in.
4. Codegen output goes into a separate `shared/contracts/` directory
   per service so users never hand-edit it.

**Acceptance.**
```bash
./contracts export
./contracts gen
ls ticket_service/shared/contracts/    # auth_api_client.py
ls web_ui/src/shared/contracts/         # ticketServiceClient.ts
```

---

## Section 6 · Observability baseline (Roadmap Phase 6.1)

### 6.1 Structured JSON logging defaults

**Why.** Roadmap Phase 6.1. Every backend should emit structured logs
with a consistent shape so a single Loki/Elasticsearch sink can ingest
them.

**Files.** Per-skel logging config:
- `_skels/python-django-skel/myproject/settings.py` (LOGGING dict).
- `_skels/python-django-bolt-skel/app/settings.py`.
- `_skels/python-fastapi-skel/core/common_logging.py` (already exists,
  needs JSON formatter).
- `_skels/python-flask-skel/app/__init__.py`.
- `_skels/java-spring-skel/src/main/resources/application.properties`
  (logback JSON encoder).
- `_skels/rust-*-skel/src/main.rs` (tracing-subscriber JSON layer).
- `_skels/js-skel/src/index.js` (pino).

**Scenario.**
1. Define a canonical envelope: `{timestamp, level, service, trace_id,
   span_id, message, ...attrs}`.
2. For each stack, wire a JSON formatter that produces the envelope.
3. Add a `LOG_FORMAT=json|console` env var in the wrapper `.env` so dev
   defaults to console-pretty and prod defaults to JSON.
4. Cross-reference with the `SERVICE_NAME` env var (already in
   `_shared/service-urls.env` via the slug).

**Acceptance.**
```bash
LOG_FORMAT=json ./run ticket_service dev | head -1 | jq .
# { "timestamp": "...", "service": "ticket_service", "level": "info", ... }
```

---

### 6.2 OpenTelemetry tracing wiring

**Why.** Roadmap Phase 6.2 — propagate `traceparent` across HTTP calls
between services so you can debug a request hop in Grafana Tempo or
Jaeger.

**Files.** Per-skel: install + initialise the OTel SDK with an OTLP
exporter pointed at `${OTEL_EXPORTER_OTLP_ENDPOINT}` (add to wrapper
`.env.example`). Plus `docker-compose.yml` gains an opt-in
`otel-collector + tempo + grafana` profile.

**Scenario.**
1. Add `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` and
   `OTEL_SERVICE_NAME` to the wrapper `.env.example`.
2. Each backend skel installs the appropriate OTel package
   (`opentelemetry-instrumentation-django`, `springdoc-otel`,
   `opentelemetry-rust`, `@opentelemetry/sdk-node`).
3. Each `main` / settings entry initialises the SDK, registering the
   FastAPI / Django / Spring middleware that auto-injects spans.
4. Add a `--profile observability` to `docker-compose.yml` that brings
   up an `otel/opentelemetry-collector-contrib` + `grafana/tempo` +
   `grafana/grafana` stack.

**Acceptance.**
```bash
docker compose --profile observability up -d
./run dev-all
curl http://localhost:8001/api/auth/login   # auth_api
# Open http://localhost:3000 (Grafana) → Tempo → search by service name
# A single trace spans auth_api → postgres → ticket_service.
```

---

## Section 7 · Project-level UX (Roadmap Phase 7)

### 7.1 `./project test` / `./project lint` / `./project build`

**Why.** Roadmap Phase 7.1. Today `./test` fans out to every service via
the dispatch wrapper, but each service uses a different test runner
(`pytest`, `cargo test`, `mvn test`, `vitest`, `node --test`). A
project-level wrapper aggregates the results into a single report.

**Files.** New `_skels/_common/project.sh` generated into
`<wrapper>/project` by `common-wrapper.sh`.

**Scenario.**
1. The script reads `dev_skel.project.yml` (item 4.1) and dispatches
   per-service `test` / `lint` / `build` scripts in parallel where
   possible.
2. Aggregates exit codes and prints a colour-coded summary:
   ```
   ==== test ====
     ✓ ticket_service     pytest         12 passed   3.1s
     ✓ auth_api           pytest          7 passed   1.4s
     ✗ java_service       mvn test       2 failed   25.4s
     ✓ edge_gateway       cargo test      4 passed   8.2s
   3/4 services passed
   ```
3. Use `make -j` style parallelism when `--jobs N` is passed.

**Acceptance.**
```bash
./project test --jobs 4
# Single command runs every service's test suite, prints aggregated
# summary, exits non-zero if any service failed.
```

---

### 7.2 `./project graph` (service dependency visualization)

**Why.** Roadmap Phase 7.2. A picture of the service mesh is the
fastest way to onboard a new contributor.

**Files.** New `_skels/_common/project-graph.sh` generator + integrate
into `./project`.

**Scenario.**
1. Read `dev_skel.project.yml` plus the auto-generated
   `_shared/service-urls.env` to derive node IDs.
2. Optionally read `services[i].depends_on` (a new metadata field) for
   edges.
3. Emit a Mermaid diagram to stdout (or `--format dot|plantuml`).
4. Add `./project graph --open` that pipes the Mermaid into
   `mermaid-cli` and opens the resulting SVG.

**Acceptance.**
```bash
./project graph
# %% mermaid
# graph LR
#   web_ui --> ticket_service
#   ticket_service --> postgres
#   ticket_service --> auth_api
#   auth_api --> postgres
```

---

## Section 8 · Skel-side polish

### 8.1 Per-skel `verify-shared-db` scripts (de-duplicates `_bin/skel-test-shared-db`)

**Why.** Today `_bin/skel-test-shared-db` ships an inline `VERIFY_SCRIPT`
Python snippet. Moving the verifier into each skel makes it
discoverable for users who want to manually exercise the env contract.

**Files.** New `verify-shared-db` script in each backend skel root.
Update `_bin/skel-test-shared-db` to call them.

**Scenario.**
1. Each backend skel ships a `verify-shared-db` bash script that:
   - Sources `.env` (it's already in the env via the dispatch wrapper).
   - Activates the local virtualenv (Python) / sets up `cargo run`
     args (Rust) / etc.
   - Runs the stack-native verifier with the seed name as $1.
2. `_bin/skel-test-shared-db` calls `<service>/verify-shared-db
   "<seed-name>"` instead of inlining `VERIFY_SCRIPT`.
3. Each skel's `verify-shared-db` is also a great manual smoke test —
   add it to the per-skel CLAUDE.md and README.

**Acceptance.**
```bash
cd myproj
./verify-shared-db ticket_service shared-db-test-row
# OK /Users/.../myproj/_shared/db.sqlite3 -> (1, 'shared-db-test-row')
```

---

### 8.2 AI manifest "items table convention" alignment

**Why.** Each ORM uses a different default table name (Django:
`<app>_<model>`, SQLAlchemy with `__tablename__`: literal,
Spring/JPA: `<entity>`). For the shared-DB integration test the
manifests already nudge towards `items` (plural snake_case), but it's
implicit. Make it a documented convention.

**Files.** Each manifest's system prompt + a new
`_docs/SHARED-DATABASE-CONVENTIONS.md`.

**Scenario.**
1. Write `_docs/SHARED-DATABASE-CONVENTIONS.md` documenting the
   schema-first contract: every shared entity must have a table named
   `<items_plural>` with at least `id`, `name`, `description`,
   `is_completed`, `created_at`, `updated_at` columns.
2. Update each AI manifest's system prompt with a one-line reference:
   "When generating models for the `{item_class}` entity, ALWAYS use
   table name `{items_plural}` and include the canonical columns from
   `_docs/SHARED-DATABASE-CONVENTIONS.md`. This is what
   `_bin/skel-test-shared-db` and downstream consumers rely on."
3. Update the Django prompts to use
   `db_table='{items_plural}'` in `class Meta`.
4. Update the Spring manifest (when 3.2 lands) to use
   `@Table(name = "{items_plural}")`.

**Acceptance.** `_bin/skel-test-shared-db` works against an AI-generated
service from any skeleton with no manual schema patching.

---

### 8.3a Extend `/api/items` + `/api/state` to django / fastapi / flask backends

**Why.** The React skeleton's `src/api/items.ts` and
`src/state/state-api.ts` call `${BACKEND_URL}/api/items` and
`${BACKEND_URL}/api/state` against the wrapper-shared `BACKEND_URL`.
**Today only `python-django-bolt-skel` exposes both endpoint
families** — it ships the `Item` model + `ItemViewSet` and the
`ReactState` model + `react_state_load` / `react_state_upsert` /
`react_state_delete` handlers out of the box, which is why
django-bolt is the React skel's default backend pairing.

**Status.** Shipped for `python-fastapi-skel` (2026-04) via the new
`app/wrapper_api/` module — see `_bin/test-react-fastapi-integration`
for the live cross-stack proof. The remaining two Python backends
(`python-django-skel`, `python-flask-skel`) still need the same
endpoints so users can swap `BACKEND_URL` to any backend service in
the wrapper without touching React code.

**Files.**
- `_skels/python-django-skel/myproject/<service>/models.py`,
  `views.py`, `urls.py` — add `Item` model, `ItemViewSet`,
  `ReactState` model + the three `/api/state` views.
- ~~`_skels/python-fastapi-skel/app/items.py`, `app/state.py` (new
  routers), `core/models.py` for the SQLAlchemy entities.~~
  **Done** — landed at `_skels/python-fastapi-skel/app/wrapper_api/`
  (`__init__.py`, `db.py`, `security.py`, `schemas.py`, `deps.py`,
  `auth.py`, `items.py`, `state.py`, `router.py`). Tables auto-create
  via `SQLModel.metadata.create_all(engine)` in `db.py`.
- `_skels/python-flask-skel/app/items.py`, `app/state.py` (new
  blueprints).
- The corresponding AI manifests
  (`_skels/_common/manifests/python-django-skel.py`,
  `python-fastapi-skel.py`, `python-flask-skel.py`) — add
  preserve-verbatim language for the new files (mirroring how the
  django-bolt manifest handles `Item` + `ReactState`).
- `_skels/python-django-bolt-skel/CLAUDE.md` and
  `_skels/ts-react-skel/CLAUDE.md` — drop the "django-bolt is the
  only backend that ships these endpoints" caveat once parity lands.

**Scenario.**
1. **Schema parity.** Match the django-bolt `Item` shape exactly
   (`id`, `name`, `description`, `is_completed`, `created_at`,
   `updated_at`, table name `items`) and the `ReactState` shape
   (per-user JSON key/value, table name `react_state`, unique on
   `(user, key)`). Cross-link to
   `_docs/SHARED-DATABASE-CONVENTIONS.md` so the schema is genuinely
   the same SQL on disk — `_bin/skel-test-shared-db` will then verify
   the new backends can read django-bolt's seed rows.
2. **Endpoint parity.** Mount the routes at exactly
   `/api/items` (CRUD + a `complete` action) and `/api/state` /
   `/api/state/{key}` (GET / PUT / DELETE). Reuse each backend's
   existing JWT middleware so the same React-issued token works
   against any of them.
3. **AI manifest hardening.** Each manifest's system prompt should
   list the new files under "MUST be preserved verbatim" the way
   the django-bolt manifest does for `Item` / `ReactState`. Also
   update the per-target prompts so the user-chosen `{item_class}`
   never collides with the canonical `Item` model.
4. **Cross-stack proof.** Extend `_bin/skel-test-shared-db` with a new
   `cross-backend round-trip` step: spin up the React frontend
   pointed at django-bolt, write an item, then re-point
   `BACKEND_URL` at fastapi (or flask, or django) and confirm the
   same item is visible. The runner already pre-seeds `items`, so
   this is mostly a `BACKEND_URL=...` env var dance plus a fetch
   from the verifier.

**Acceptance.**
```bash
make gen-django   NAME=myproj SERVICE='Auth API'
make gen-fastapi  NAME=myproj SERVICE='Inventory'
make gen-react    NAME=myproj SERVICE='Web UI'
cd myproj
# Point the frontend at the django service for items + state…
sed -i '' 's|^BACKEND_URL=.*|BACKEND_URL=http://localhost:8001|' .env
./run web_ui dev   # React UI now talks to django, not django-bolt
# …or at fastapi.
sed -i '' 's|^BACKEND_URL=.*|BACKEND_URL=http://localhost:8002|' .env
./run web_ui dev
```
The `useItems` and `useAppState` flows work against every backend
without any React code changes.

---

### 8.3 Migration coordination across backends

**Why.** Each backend has its own migration system (Django migrations,
Alembic, Flyway, sqlx-migrate, Prisma). Without coordination, two
backends generating migrations for the same shared `items` table will
collide.

**Files.** New `_skels/_common/migrations/` shared SQL directory,
`_bin/migrate-shared` runner, per-skel hooks.

**Scenario.**
1. Establish a single source of truth for the shared schema:
   `<wrapper>/_shared/migrations/NNNN_<name>.sql` files (plain SQL,
   no per-stack DSL).
2. Add `_bin/migrate-shared` Python script that:
   - Reads `_shared/migrations/*.sql` in order.
   - Tracks applied migrations in `_shared/_migrations_applied.txt`.
   - Runs each unapplied migration via `sqlite3` (or `psycopg2` for
     postgres).
3. Each backend's migration system is configured to **skip** the
   shared `items` table — they only manage service-specific tables.
4. Document the convention in `_docs/SHARED-DATABASE-CONVENTIONS.md`
   (item 8.2).

**Acceptance.**
```bash
echo "ALTER TABLE items ADD COLUMN priority TEXT" > _shared/migrations/0002_add_priority.sql
./migrate-shared
# Applied 0002_add_priority.sql
make test-shared-db   # every backend sees the new column
```

---

## Section 9 · Documentation polish

### 9.1 Migration guide: legacy `backend-1/` → service-name dirs

**Why.** Anyone with a wrapper generated **before** the service-name
flow has directories like `backend-1`, `frontend-1` etc. The new
shared-env flow assumes slugs like `ticket_service`. They need a
migration path.

**Files.** New `_docs/MIGRATING-FROM-LEGACY-DIRS.md`.

**Scenario.**
1. Document the rename script:
   ```bash
   cd myproj
   mv backend-1 ticket_service
   # Update any per-service .env that hardcodes the old path
   ./services   # confirm new slug is discovered
   ```
2. Note that the wrapper-shared `.env` and `_shared/` survive the
   rename untouched.
3. Cover the AI manifest case: `_bin/skel-gen-ai --skip-base
   --service-name 'Ticket Service'` against an existing project picks
   up the new slug correctly.

**Acceptance.** A user with a pre-2026 wrapper can run the documented
steps and end up with a working multi-service project on the new
contract.

---

### 9.2 Wrapper README: "Cookbook" section

**Why.** The current wrapper README explains the layout but doesn't
walk through realistic recipes (add a service, switch to Postgres, run
the shared-DB test, regenerate after editing the AI manifest).

**Files.** `_skels/_common/common-wrapper.sh` (the wrapper README
generation block at line ~165).

**Scenario.**
1. Append a `## Cookbook` section to the generated wrapper README with
   3–4 recipes:
   - **Add a new service to the project** — `make gen-X NAME=. SERVICE='...'`.
   - **Switch to Postgres** — `docker compose up postgres -d` + edit
     `.env`.
   - **Run the shared-DB integration test** —
     `make -C $DEV_SKEL test-shared-db` (assuming dev_skel is on
     `$PATH`).
   - **AI-generate a new entity into an existing service** — `_bin/skel-gen-ai
     <skel> myproj --skip-base --service-name '...'`.
2. Each recipe is 5–10 lines with a bash block.

**Acceptance.** The generated `<wrapper>/README.md` is opinionated and
scannable; new contributors can follow the cookbook without needing to
read the full repo README.

---

## Index · Suggested execution order

To deliver value incrementally:

1. **Section 1 (1.1, 1.2, 1.3)** — small follow-ups, < 1 day total.
2. **Section 2.3** — wire the existing test-shared-db into CI
   (cheapest way to lock in the recent gains).
3. **Section 2.1, 2.2** — postgres + per-runtime ORM exercise in the
   integration test (medium effort, high signal).
4. **Section 4.1, 4.2** — `dev_skel.project.yml` + `./services info`
   (unblocks every Roadmap phase from 2 onwards).
5. **Section 8.3a** — extend `/api/items` + `/api/state` to django /
   fastapi / flask so the React frontend can swap `BACKEND_URL` to
   any backend in the wrapper without code changes (currently only
   django-bolt ships both endpoint families).
6. **Section 3.1a** — roll out `INTEGRATION_MANIFEST` to the other
   8 skels so every `_bin/skel-gen-ai` run produces integration
   code + tests (currently only `python-django-bolt-skel` ships one).
7. **Section 3.2** — AI manifest hardening for the freshly-landed
   Java / Rust / JS / React manifests (Section 3.1 is now complete).
8. **Section 5.1, 5.2** — contract-driven codegen.
9. **Section 4.3, 4.4** — `./run dev-all` + reverse-proxy gateway.
10. **Section 6** — observability baseline.
11. **Section 7** — project-level UX.
12. **Section 8, 9** — schema convention + docs polish (can land any
    time after Section 4).

## Notes

- This file is the **practical** counterpart to `ROADMAP.md`. The
  roadmap captures the long-term vision; this file captures specific
  PRs that move dev_skel toward it.
- Each section is self-contained: pick one item, ship it, mark it done
  here, move on. Avoid bundling multiple sections into a single PR.
- When closing an item, prefer adding a one-line "**Done in commit
  abcdef0**" line under the acceptance check rather than deleting the
  entry — the historical record helps future contributors understand
  why a particular convention exists.
