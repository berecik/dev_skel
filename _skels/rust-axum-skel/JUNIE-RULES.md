# Junie Rules for `rust-axum-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`rust-axum-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Rust backend skeleton using Axum.
- Lives at `_skels/rust-axum-skel/`.
- Uses `cargo new` then overlays additional files via `merge`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Rust toolchains and key Axum ecosystem crates reasonably up to date.
3. Ensure generated projects are idiomatic for Axum and easy to extend.

---

## 2. Files to Check First

When working on `rust-axum-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/rust-axum-skel.md` (if present).
2. Skeleton Makefile: `_skels/rust-axum-skel/Makefile`.
3. Generator scripts:
   - `_skels/rust-axum-skel/gen`
   - `_skels/rust-axum-skel/merge`
   - `_skels/rust-axum-skel/test_skel`
4. Dependency installers:
   - `_skels/rust-axum-skel/deps`
   - `_skels/rust-axum-skel/install-deps`
5. Cargo files and source code:
   - `_skels/rust-axum-skel/Cargo.toml`
   - `_skels/rust-axum-skel/src/`.

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Rust and Axum)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the **current calendar date** to reason about which Rust stable
   release and Axum ecosystem versions are "current".
2. Prefer the latest stable Rust toolchain (via `rustup`) that is compatible
   with Axum and the ecosystem.
3. For dependencies in `Cargo.toml`:
   - Prefer stable crate versions.
   - Review release notes before upgrading major versions of Axum or
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

1. Do **not** remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do **not** hard-code environment-specific paths or assumptions beyond what
   the `deps` script guarantees.
3. Do **not** upgrade Rust or Axum crates in a way that breaks generator
   tests without addressing resulting issues.
