# Claude Code Rules — `ts-react-skel`

Claude-specific complement to `_skels/ts-react-skel/AGENTS.md` and
`_skels/ts-react-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/ts-react-skel/CLAUDE.md` (this file)
2. `_skels/ts-react-skel/AGENTS.md`
3. `_skels/ts-react-skel/JUNIE-RULES.md`
4. `_docs/ts-react-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- React + Vite + TypeScript SPA frontend with Vitest, ESLint, Prettier.
- Generated services live under `<wrapper>/frontend-1/`,
  `<wrapper>/frontend-2/`, ...
- The generator runs `npm create vite@latest` and overlays skeleton
  files. The merge script **excludes** these generator-owned files —
  do not copy or rewrite them from the skeleton:
  - `package.json`
  - `package-lock.json`
  - `tsconfig.json`
  - `tsconfig.node.json`
  - `vite.config.ts`

---

## 3. Claude Operational Notes

1. **Always `Read` before editing.** Never modify the generator-owned files
   listed above through the skeleton; if you need to change them, change the
   `gen` / `merge` scripts so the generator handles it.
2. **Plan dependency bumps** that touch React, Vite, TypeScript, or
   testing libraries; confirm scope with the user before editing pinned
   versions.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/ts-react-skel && make test
   ```
4. Never hand-edit `_test_projects/test-react-app` — regenerate with
   `make gen-react NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (includes a `npm run build`).
- [ ] React skeleton-specific tests pass.
- [ ] No generator-owned files were hand-edited or copied via merge.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
