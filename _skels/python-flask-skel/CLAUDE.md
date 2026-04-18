# Claude Code Rules — `python-flask-skel`

Claude-specific complement to `_skels/python-flask-skel/AGENTS.md` and
`_skels/python-flask-skel/JUNIE-RULES.md`. Read those first.


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

1. `_skels/python-flask-skel/CLAUDE.md` (this file)
2. `_skels/python-flask-skel/AGENTS.md`
3. `_skels/python-flask-skel/JUNIE-RULES.md`
4. `_docs/python-flask-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Lightweight Flask (WSGI) backend. Generates into `<wrapper>/backend-1/`
  and friends.
- Keep the demo footprint small — avoid pulling in heavy extensions unless
  the user explicitly asks.

---

## 3. Claude Operational Notes

1. **`Read` before editing** any file in `app/` or the skeleton generator
   scripts.
2. **Plan dependency bumps** that change Flask, Werkzeug, or Jinja
   versions and confirm with the user before editing pinned versions.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/python-flask-skel && make test
   ```
4. Never hand-edit `_test_projects/test-flask-app` — regenerate with
   `make gen-flask NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] Flask skeleton-specific tests pass.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
