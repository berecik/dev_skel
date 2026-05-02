# Junie Rules for `rust-actix-ddd-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`rust-actix-ddd-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Rust backend skeleton using Actix Web.
- Lives at `_skels/rust-actix-ddd-skel/`.
- Uses `cargo new` then overlays additional files via `merge`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Rust toolchains and key Actix ecosystem crates reasonably up to
   date.
3. Ensure generated projects are idiomatic for Actix and easy to extend.

---

## 2. Files to Check First

When working on `rust-actix-ddd-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/rust-actix-skel.md` (if present).
2. Skeleton Makefile: `_skels/rust-actix-ddd-skel/Makefile`.
3. Generator scripts:
   - `_skels/rust-actix-ddd-skel/gen`
   - `_skels/rust-actix-ddd-skel/merge`
   - `_skels/rust-actix-ddd-skel/test_skel`
4. Dependency installers:
   - `_skels/rust-actix-ddd-skel/deps`
   - `_skels/rust-actix-ddd-skel/install-deps`
5. Cargo files and source code:
   - `_skels/rust-actix-ddd-skel/Cargo.toml`
   - `_skels/rust-actix-ddd-skel/src/`.

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Rust and Actix)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the **current calendar date** to reason about which Rust stable
   release and Actix ecosystem versions are "current".
2. Prefer the latest stable Rust toolchain (via `rustup`) that is compatible
   with Actix and the ecosystem.
3. For dependencies in `Cargo.toml`:
   - Prefer stable crate versions.
   - Review release notes before upgrading major versions of Actix Web or
     related crates.
4. Do **not** fabricate version numbers. If you cannot confirm current
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

1. Follow idiomatic Actix patterns for server setup, routes, and handlers.
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

Generated Rust/Actix test projects under `_test_projects/` should:

1. Build successfully with `cargo`.
2. Run their tests successfully using the generated `./test` script.

If these expectations cannot be met, document the reason in the relevant
docs file for this skeleton.

---

## 6. Do Not

1. Do **not** remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do **not** hard-code environment-specific paths or assumptions beyond what
   the `deps` script guarantees.
3. Do **not** upgrade Rust or Actix crates in a way that breaks generator
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
