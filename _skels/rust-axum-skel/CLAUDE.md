# Claude Code Rules — `rust-axum-skel`

Claude-specific complement to `_skels/rust-axum-skel/AGENTS.md` and
`_skels/rust-axum-skel/JUNIE-RULES.md`. Read those first.


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

1. `_skels/rust-axum-skel/CLAUDE.md` (this file)
2. `_skels/rust-axum-skel/AGENTS.md`
3. `_skels/rust-axum-skel/JUNIE-RULES.md`
4. `_docs/rust-axum-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Rust Axum service skeleton (ergonomic web framework on top of Tokio).
  Generates into `<wrapper>/<service_slug>/` (or `<wrapper>/service/`
  when no service name is given).
- The generator runs `cargo new` then overlays skeleton files. The merge
  script **excludes** `Cargo.toml` and `src/main.rs` — do not weaken those
  exclusions.
- **Shared env contract** (CRITICAL): `src/config.rs` exposes a `Config`
  struct populated by `Config::from_env()` from `DATABASE_URL`,
  `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`, `SERVICE_HOST`, and `SERVICE_PORT`. The
  `load_dotenv()` helper walks up to `<wrapper>/.env` so child processes
  inherit the wrapper-shared environment. The `Config` is held inside
  `AppState` and reachable from handlers via
  `State(Arc<AppState>)`. Do not re-read `std::env::var` directly in
  handler code — go through the `Config`. Never hardcode a JWT secret or
  database URL.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `src/`, `Cargo.toml`, or
   the skeleton generator scripts.
2. **Plan crate version bumps** and run `cargo update` inside the skeleton
   when refreshing the lockfile. Confirm scope with the user for major
   Axum, Tokio, or Hyper upgrades.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/rust-axum-skel && make test
   ```
4. Never hand-edit `_test_projects/test-axum-app` — regenerate with
   `make gen-axum NAME=_test_projects/<name>`.
5. Keep `cargo build --release` clean before declaring the change done.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (`cargo build --release` passes).
- [ ] Axum skeleton-specific tests pass.
- [ ] No generator-owned files (`Cargo.toml`, `src/main.rs`) were
      hand-edited via the merge path.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
