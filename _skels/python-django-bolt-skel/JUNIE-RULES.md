# Junie Rules for `python-django-bolt-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`python-django-bolt-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files, plus the cross-agent
`_skels/python-django-bolt-skel/AGENTS.md`. Where this file omits a topic,
fall back to the global rules and the AGENTS.md baseline.

---

## 1. Purpose of This Skeleton

- Django backend skeleton built on **django-bolt** (Rust HTTP layer via
  Actix Web + PyO3) and **msgspec.Struct** schemas.
- Lives at `_skels/python-django-bolt-skel/`.
- Generates test projects under `_test_projects/test-django-bolt-app`.
- Mirrors the layout of `claude_on_django`-generated projects so the AI
  manifest at `_skels/_common/manifests/python-django-bolt-skel.py` can
  rewrite the same set of files.

Goals when editing:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   `./build-dev`, `./install-deps`).
2. Keep django-bolt and msgspec on broadly supported releases.
3. Preserve the layered structure that the AI manifest assumes.

---

## 2. Files to Check First

1. Skeleton README: `_skels/python-django-bolt-skel/README.md`
2. Skeleton Makefile: `_skels/python-django-bolt-skel/Makefile`
3. Generator scripts:
   - `_skels/python-django-bolt-skel/gen`
   - `_skels/python-django-bolt-skel/merge`
   - `_skels/python-django-bolt-skel/test_skel`
4. Dependency installers:
   - `_skels/python-django-bolt-skel/deps`
   - `_skels/python-django-bolt-skel/install-deps`
5. Source code under `_skels/python-django-bolt-skel/app/`
6. AI manifest: `_skels/_common/manifests/python-django-bolt-skel.py`

Do **not** edit `_test_projects/*` directly.

---

## 3. Architecture Constraints (Quick Recap)

- Routing comes from `BoltAPI` decorators in `app/api.py`. `app/urls.py` is
  intentionally empty.
- Schemas are `msgspec.Struct` only. Do **not** use DRF serializers.
- Auth uses `create_jwt_for_user` and `Token.decode` from `django_bolt`.
- Endpoints are `async def`; ORM access is async (`aget`, `acreate`,
  `asave`, `adelete`).
- The Django app is called `app`. Renaming requires updating
  `app.settings`, `manage.py`, `conftest.py`, the AI manifest, and tests.

---

## 4. Testing Expectations

For non-trivial changes:

```bash
make clean-test
make test-generators
```

For skeleton-scoped changes:

```bash
make test-gen-django-bolt
make test-django-bolt
```

---

## 5. Do Not

1. Do not remove or drastically alter the generator entrypoints.
2. Do not hand-edit files that the AI manifest regenerates — update the
   manifest prompt and re-run `_bin/skel-gen-ai python-django-bolt-skel ...`.
3. Do not pull in djangorestframework, simplejwt, django-filter, or other
   DRF-ecosystem packages.
4. Do not modify `_test_projects/` by hand.
