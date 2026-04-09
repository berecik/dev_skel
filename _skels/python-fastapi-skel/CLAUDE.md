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

## 4. Ollama AI generator (`skel-gen-ai`)

This skeleton has a manifest at
`_skels/_common/manifests/python-fastapi-skel.py` consumed by
`_bin/skel-gen-ai`. The manifest treats the existing `app/example_items/`
module as the canonical reference and asks Ollama to rewrite it as a new
`app/{service_slug}/` module with the user's `{item_class}` entity.

Generated targets:

- `app/{service_slug}/__init__.py`
- `app/{service_slug}/models.py` (Pydantic + abstract repository / CRUD / UoW)
- `app/{service_slug}/adapters/__init__.py`
- `app/{service_slug}/adapters/sql.py` (SQLModel concrete layer)
- `app/{service_slug}/depts.py` (FastAPI dependency providers)
- `app/{service_slug}/routes.py` (APIRouter endpoints)
- `app/{service_slug}/tests/__init__.py`

Operational notes:

1. After generation, register the new module by adding
   `router.include_router({service_slug}_routes.router,
   tags=['{items_plural}'], prefix='/{items_plural}')` to `app/routes.py`.
   `skel-gen-ai` does not modify `app/routes.py` automatically — keep that
   manual step explicit so reviewers can audit it.
2. When `auth_type == 'none'` the prompts drop the `current_user`
   dependency and owner-isolation checks. For any other auth style, the
   reference's `core.deps.CurrentUser` flow is preserved verbatim.
3. To change the layered DDD layout (models / adapters / depts / routes),
   edit the manifest, not the generated files. Re-run with
   `--skip-base --dry-run` first to confirm the target list still resolves.

---

## 5. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] FastAPI skeleton-specific tests pass.
- [ ] AI manifest still loads and renders prompts.
- [ ] AGENTS.md / CLAUDE.md / JUNIE-RULES.md still agree.
- [ ] No generator-owned files were hand-edited.
