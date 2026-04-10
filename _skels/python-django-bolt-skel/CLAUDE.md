# Claude Code Rules — `python-django-bolt-skel`

Claude-specific complement to `_skels/python-django-bolt-skel/AGENTS.md`
and `_skels/python-django-bolt-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/python-django-bolt-skel/CLAUDE.md` (this file)
2. `_skels/python-django-bolt-skel/AGENTS.md`
3. `_skels/python-django-bolt-skel/JUNIE-RULES.md`
4. `_skels/python-django-bolt-skel/README.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Django + django-bolt (Actix Web + PyO3, ~60k RPS) backend skeleton with
  msgspec.Struct schemas, JWT/OAuth auth helpers, and async ORM endpoints.
- Generated services live under `<wrapper>/<service_slug>/` (e.g. when
  the user types `"Ticket Service"` the dir is `myproj/ticket_service/`).
  Defaults to `<wrapper>/backend/` when no service name is supplied.
- The Django app is named `app`. `ROOT_URLCONF = 'app.urls'` and
  `app.urls.urlpatterns = []` — every endpoint lives on the `BoltAPI()`
  instance in `app/api.py`.
- **Shared env contract** (CRITICAL): `app/settings.py` loads
  `<wrapper>/.env` first, then the local service `.env`. JWT material
  comes from `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_ISSUER` /
  `JWT_ACCESS_TTL` / `JWT_REFRESH_TTL` env vars. The DB is resolved by
  `_build_databases()` from `DATABASE_URL` (default
  `sqlite:///<wrapper>/_shared/db.sqlite3`). `auth_service.py` calls
  `create_jwt_for_user(...)` and `Token.decode(...)` with
  `settings.JWT_SECRET` — **never** with `settings.SECRET_KEY`.
- **Default React backend** (CRITICAL): this skel is the **default
  backend the `ts-react-skel` frontend talks to** via the wrapper-
  shared `BACKEND_URL`. Two cross-stack endpoints MUST stay intact:
  - `/api/items` — `Item` model (table `items`, fields `name`,
    `description`, `is_completed`, `created_at`, `updated_at`) +
    `ItemViewSet` mounted at `/api/items` via `BoltAPI`. The React
    skeleton's `src/api/items.ts` calls `${config.backendUrl}/api/items`
    against this. The model + schemas + viewset are kept verbatim
    by the AI manifest even when the user picks a different
    `{item_class}` to scaffold.
  - `/api/state` — `ReactState` model (table `react_state`, per-user
    JSON key/value store) + `react_state_load` (GET `/api/state`),
    `react_state_upsert` (PUT `/api/state/{key}`), and
    `react_state_delete` (DELETE `/api/state/{key}`) handlers. The
    React skeleton's `src/state/state-api.ts` calls these so the
    `useAppState<T>(key, default)` hook can persist UI slices
    (filters, sort order, preferences) across sessions. Same rule:
    the AI manifest keeps these handlers verbatim.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file in `app/` or the skeleton
   generator scripts.
2. **Plan large changes.** Touching `models.py` cascades through `schemas.py`,
   `api.py`, and the test files. Draft a Plan first when more than one of
   those files is in scope, and confirm with the user before editing pinned
   versions in `requirements.txt`.
3. **Use the AI manifest.** This skeleton has a manifest at
   `_skels/_common/manifests/python-django-bolt-skel.py`. The preferred
   workflow for adding a brand-new entity is to update the user dialog
   answers and re-run `_bin/skel-gen-ai python-django-bolt-skel myproj
   backend --skip-base ...`, not to hand-edit the generated files.
4. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/python-django-bolt-skel && make test
   ```
5. Never hand-edit `_test_projects/test-django-bolt-app` — regenerate with
   `make gen-django-bolt NAME=_test_projects/<name>`.
6. Keep `python manage.py check` clean before declaring the change done.
7. Prefer dedicated tools (`Read`, `Edit`, `Write`, `Glob`, `Grep`) over
   `Bash`. Reach for `Bash` only for `make`, `pytest`, `manage.py`, or git.

---

## 4. Ollama AI generator (`skel-gen-ai`)

The manifest at `_skels/_common/manifests/python-django-bolt-skel.py`
regenerates this set of files in the new project:

- `app/models.py` (UserProfile, Project, **Item**, **ReactState**, plus
  the user-chosen `{item_class}`)
- `app/schemas.py` (msgspec.Struct equivalents with `from_model` helpers)
- `app/services/auth_service.py` (JWT register/login/oauth/refresh)
- `app/api.py` (BoltAPI endpoints + ModelViewSets for the user's entity)
- `app/tests/test_models.py` and `app/tests/test_api.py`

Operational notes:

1. Edit prompts in the manifest, not the generated files. After tweaking
   prompts, run `_bin/skel-gen-ai python-django-bolt-skel <proj> backend
   --no-input --skip-base --dry-run` against an existing test project to
   confirm the target list still resolves before doing a real generation.
2. The auth-style branch (`{auth_type}`) only affects `api.py` and
   `auth_service.py`. The Project / Task / UserProfile models stay
   owner-aware regardless because django-bolt always assumes a `User`.
3. **The `Item` model + `ItemViewSet` (mounted at `/api/items`) and
   the `ReactState` model + `react_state_load` / `react_state_upsert` /
   `react_state_delete` handlers (mounted at `/api/state`) MUST be
   preserved verbatim by the manifest** — they back the wrapper-shared
   contract the React frontend consumes. The system prompt and the
   per-target prompts in the manifest spell this out explicitly; if
   you tweak the prompts, re-verify with a dry-run that the
   preservation language is still in place.
4. After generation, run `python manage.py makemigrations app && python
   manage.py migrate` yourself — `skel-gen-ai` does not touch Django
   commands.

---

## 5. Verification Checklist

- [ ] `make test-generators` is green (specifically `test-gen-django-bolt`).
- [ ] Skeleton-scoped tests pass: `make test-django-bolt`.
- [ ] AI manifest still loads and renders prompts (`python3 -c "...
      load_manifest(..., 'python-django-bolt-skel')"`).
- [ ] No DRF / simplejwt / django-filter packages were added.
- [ ] `Item` model + `ItemViewSet` and `ReactState` model + the three
      `react_state_*` handlers are still present in `app/models.py`,
      `app/schemas.py`, and `app/api.py` (regenerate with the AI
      manifest if a refactor accidentally drops them).
- [ ] `_bin/skel-test-shared-db --skel python-django-bolt-skel` is green.
- [ ] AGENTS.md / CLAUDE.md / JUNIE-RULES.md still agree with the
      implementation.
