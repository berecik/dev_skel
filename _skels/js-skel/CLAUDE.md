# Claude Code Rules — `js-skel`

Claude-specific complement to `_skels/js-skel/AGENTS.md` and
`_skels/js-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/js-skel/CLAUDE.md` (this file)
2. `_skels/js-skel/AGENTS.md`
3. `_skels/js-skel/JUNIE-RULES.md`
4. `_docs/js-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Plain Node.js / JavaScript skeleton (used for backend tools, scripts,
  or simple Node services). Generates into `<wrapper>/app-1/` or
  `<wrapper>/service-1/`.

---

## 3. Claude Operational Notes

1. **`Read` before editing** any source file or generator script.
2. **Plan dependency bumps** (npm packages, Node version) and confirm
   scope with the user before editing `package.json`.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/js-skel && make test
   ```
4. Never hand-edit `_test_projects/test-js-app` — regenerate with
   `make gen-js NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] JS skeleton-specific tests pass.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
