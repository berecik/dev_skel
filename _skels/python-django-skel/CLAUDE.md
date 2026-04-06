# Claude Code Rules — `python-django-skel`

Claude-specific complement to `_skels/python-django-skel/AGENTS.md` and
`_skels/python-django-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/python-django-skel/CLAUDE.md` (this file)
2. `_skels/python-django-skel/AGENTS.md`
3. `_skels/python-django-skel/JUNIE-RULES.md`
4. `_docs/python-django-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Classic Django backend (batteries included). Generates into
  `<wrapper>/backend-1/` and friends.
- The generator runs `django-admin startproject` then overlays skeleton
  files; the `merge` script excludes `manage.py` and key `myproject/*`
  files. Do not weaken those exclusions.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `core/`, `app/`, `myproject/`,
   or the skeleton generator scripts.
2. **Plan settings/migration changes.** Touching `settings.py`, models, or
   migrations cascades through the generated test projects — draft a Plan
   and confirm scope with the user.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/python-django-skel && make test
   ```
4. Never hand-edit `_test_projects/test-django-app` — regenerate with
   `make gen-django NAME=_test_projects/<name>`.
5. Keep `manage.py check` clean before declaring the change done.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] Django skeleton-specific tests pass.
- [ ] No generator-owned files (`manage.py`, key `myproject/*`) were
      hand-edited.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
