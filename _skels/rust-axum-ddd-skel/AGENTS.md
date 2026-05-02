# Agents Rules for `rust-axum-ddd-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`rust-axum-ddd-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.


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

## 1. Purpose of This Skeleton

- Provides a Rust backend skeleton using Axum.
- Lives at `_skels/rust-axum-ddd-skel/`.
- Uses `cargo new` then overlays additional files via `merge`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Rust toolchains and key Axum ecosystem crates reasonably up to date.
3. Ensure generated projects are idiomatic for Axum and easy to extend.

---

## 2. Files to Check First

When working on `rust-axum-ddd-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/rust-axum-skel.md` (if present).
2. Skeleton Makefile: `_skels/rust-axum-ddd-skel/Makefile`.
3. Generator scripts:
   - `_skels/rust-axum-ddd-skel/gen`
   - `_skels/rust-axum-ddd-skel/merge`
   - `_skels/rust-axum-ddd-skel/test_skel`
4. Dependency installers:
   - `_skels/rust-axum-ddd-skel/deps`
   - `_skels/rust-axum-ddd-skel/install-deps`
5. Cargo files and source code:
   - `_skels/rust-axum-ddd-skel/Cargo.toml`
   - `_skels/rust-axum-ddd-skel/src/`.

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Rust and Axum)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the current calendar date to reason about which Rust stable
   release and Axum ecosystem versions are "current".
2. Prefer the latest stable Rust toolchain (via `rustup`) that is compatible
   with Axum and the ecosystem.
3. For dependencies in `Cargo.toml`:
   - Prefer stable crate versions.
   - Review release notes before upgrading major versions of Axum or
     related crates.
4. Do not fabricate version numbers. If you cannot confirm current
   versions, keep existing versions and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

You may also run `cargo update` within the skeleton to refresh `Cargo.lock`
when appropriate.

---

## 4. Architecture and Style Constraints

1. Follow idiomatic Axum patterns for router setup, handlers, and
   application state.
2. Keep example endpoints minimal but realistic, mirroring existing patterns
   in `src/main.rs` and tests.
3. Avoid introducing non-standard patterns or heavy abstractions without
   updating documentation and tests.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

Generated Rust/Axum test projects under `_test_projects/` should:

1. Build successfully with `cargo`.
2. Run their tests successfully using the generated `./test` script.

If these expectations cannot be met, document the reason in the relevant
docs file for this skeleton.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do not hard-code environment-specific paths or assumptions beyond what
   the `deps` script guarantees.
3. Do not upgrade Rust or Axum crates in a way that breaks generator
   tests without addressing resulting issues.

---

## DDD Layer Rules (this skeleton uses the FastAPI shape)

This is a DDD-flavored sister skeleton. The HTTP contract is identical
to its flat counterpart, but the source layout follows the canonical
FastAPI shape. Every resource (`items`, `categories`, `orders`,
`catalog`, `state`) is a self-contained module with the same
five-file split:

| File | Role |
| --- | --- |
| `models` (or `dto/`) | DTOs only — request/response shapes |
| `repository` | abstract interface (Get/List/Save/Update/Delete) |
| `adapters/sql` | concrete impl — the only file that touches the ORM/connection |
| `service` | business logic, constructed with a repository (never a DB) |
| `depts` | composition root: builds adapter → service |
| `routes` | HTTP layer: pulls the service, calls one method, never touches the DB |

Cross-resource modules:

- `auth/` — flat (not CRUD); depends on `users.UserRepository`.
- `users/` — repo-only; no service, no public routes. Consumed by
  `auth/` and `seed/` only.
- `shared/` — `errors` (DomainError sentinels), `httpx`
  (jsonError + wrapResponse), `repository` (abstract Repository<T,ID>
  + AbstractUnitOfWork).

When editing this skeleton:

1. **Stay in the resource module.** Adding a new endpoint to `items`?
   Edit `items/{models,service,depts,routes,adapters/sql}`. Don't
   reach into another resource's adapter.
2. **Services take repositories, never DB connections.** New
   collaborator? Inject another repository.
3. **Routes never touch the DB.** They call services. The DB import in
   a routes file is a smell.
4. **DTOs are explicit.** Don't return ORM entities from services.
5. **`depts` is the only place that wires the stack.** `main` (or
   the App Router `route` files, or `Application.java`) imports
   `depts`, never adapters.
6. **Domain errors flow through `shared.DomainError`.** Throw the
   sentinel; let the HTTP layer translate to status codes.

Full reference: [`_docs/DDD-SKELETONS.md`](../../_docs/DDD-SKELETONS.md).
