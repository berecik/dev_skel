# Claude Code Rules — `rust-actix-skel`

Claude-specific complement to `_skels/rust-actix-skel/AGENTS.md` and
`_skels/rust-actix-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/rust-actix-skel/CLAUDE.md` (this file)
2. `_skels/rust-actix-skel/AGENTS.md`
3. `_skels/rust-actix-skel/JUNIE-RULES.md`
4. `_docs/rust-actix-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Rust Actix-web service skeleton (fast HTTP services / quick APIs /
  edge services). Generates into `<wrapper>/service-1/` and friends.
- The generator runs `cargo new` then overlays skeleton files. The merge
  script **excludes** `Cargo.toml` and `src/main.rs` — do not weaken those
  exclusions.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `src/`, `Cargo.toml`, or
   the skeleton generator scripts.
2. **Plan crate version bumps** and run `cargo update` inside the
   skeleton when refreshing the lockfile. Confirm scope with the user
   for major Actix or Tokio upgrades.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/rust-actix-skel && make test
   ```
4. Never hand-edit `_test_projects/test-actix-app` — regenerate with
   `make gen-actix NAME=_test_projects/<name>`.
5. Keep `cargo build --release` clean before declaring the change done.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (`cargo build --release` passes).
- [ ] Actix skeleton-specific tests pass.
- [ ] No generator-owned files (`Cargo.toml`, `src/main.rs`) were
      hand-edited via the merge path.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
