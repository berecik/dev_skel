# Claude Code Rules — `python-fastapi-skel`

Claude-specific complement to `_skels/python-fastapi-skel/AGENTS.md` and
`_skels/python-fastapi-skel/JUNIE-RULES.md`. Read those first; sections
below only add Claude Code conventions.

---

## 1. Read These Files First (in order)

1. `_skels/python-fastapi-skel/CLAUDE.md` (this file)
2. `_skels/python-fastapi-skel/AGENTS.md`
3. `_skels/python-fastapi-skel/JUNIE-RULES.md`
4. `_docs/python-fastapi-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- FastAPI backend skeleton with async SQLAlchemy and a layered DDD-style
  layout.
- Generators write into `_test_projects/test-fastapi-app` and
  `_test_projects/test-fastapi-ddd-app`.
- Generated services live under `<wrapper>/backend-1/`,
  `<wrapper>/backend-2/`, ... (numeric suffixes assigned by `skel-gen`).

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `app/`, `core/`, or the
   skeleton's generator scripts.
2. **Plan dependency bumps.** FastAPI / Pydantic / SQLAlchemy upgrades touch
   many files — draft a Plan first and confirm scope with the user before
   editing `pyproject.toml` or `requirements.txt`.
3. **Use Task tracking** for any change touching more than one of: routes,
   models, config, generator scripts, or the merge exclusion list.
4. **Default validation after edits** (run via `Bash`, not via subagents):
   ```bash
   make clean-test
   make test-generators
   cd _skels/python-fastapi-skel && make test
   ```
5. **Do not hand-edit** `_test_projects/test-fastapi-*` — regenerate with
   `make gen-fastapi NAME=_test_projects/<name>` instead.
6. Keep async patterns consistent — prefer async endpoints and async DB
   access throughout.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] FastAPI skeleton-specific tests pass.
- [ ] AGENTS.md / CLAUDE.md / JUNIE-RULES.md still agree.
- [ ] No generator-owned files were hand-edited.
