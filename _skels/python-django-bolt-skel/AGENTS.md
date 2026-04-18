# Agents Rules for `python-django-bolt-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`python-django-bolt-skel` skeleton.

Always read these rules **after** the global `/AGENTS.md`,
`_docs/JUNIE-RULES.md`, and `_docs/LLM-MAINTENANCE.md` files. Claude Code
should additionally read `_skels/python-django-bolt-skel/CLAUDE.md`.


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

## 1. Purpose of This Skeleton

- Provides a Django backend skeleton built on **django-bolt** (Actix Web +
  PyO3) and **msgspec.Struct** schemas. It is the dev_skel-native version of
  the project that `claude_on_django` generates, so the file layout and
  patterns intentionally match.
- Lives at `_skels/python-django-bolt-skel/`.
- Generates test projects under `_test_projects/test-django-bolt-app`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`).
2. Keep django-bolt, msgspec, and Django on broadly supported releases.
3. Preserve the layered structure (`models.py`, `schemas.py`, `api.py`,
   `services/auth_service.py`) so the AI manifest at
   `_skels/_common/manifests/python-django-bolt-skel.py` keeps working.

---

## 2. Files to Check First

When working on `python-django-bolt-skel`, always inspect these files first:

1. Skeleton documentation: `_skels/python-django-bolt-skel/README.md`.
2. Skeleton Makefile: `_skels/python-django-bolt-skel/Makefile`.
3. Generator scripts:
   - `_skels/python-django-bolt-skel/gen`
   - `_skels/python-django-bolt-skel/merge`
   - `_skels/python-django-bolt-skel/test_skel`
4. Dependency installers:
   - `_skels/python-django-bolt-skel/deps`
   - `_skels/python-django-bolt-skel/install-deps`
5. Source code under `_skels/python-django-bolt-skel/app/`:
   - `settings.py`, `urls.py`
   - `models.py`, `schemas.py`, `api.py`
   - `services/auth_service.py`
   - `tests/test_models.py`, `tests/test_api.py`
6. AI manifest: `_skels/_common/manifests/python-django-bolt-skel.py`.

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Architecture and Style Constraints

1. **Routing is decorator-driven.** `app/urls.py` is intentionally empty
   (`urlpatterns = []`). Every endpoint lives on the `BoltAPI` instance in
   `app/api.py` via `@api.post(...)`, `@api.viewset(...)`, or `@action(...)`.
   Do not introduce a Django REST Framework router or `urls.py` route table.
2. **Schemas are msgspec.Struct only.** Do not introduce DRF serializers,
   Pydantic, or marshmallow. The whole point of this skeleton is the
   ~5–10× speedup msgspec gives the django-bolt Rust layer.
3. **Auth uses django-bolt's stateless primitives.** Use
   `create_jwt_for_user` / `Token.decode` from `django_bolt`. Do **not**
   bring in `djangorestframework-simplejwt`, `pyjwt`, or anything similar.
4. **Async ORM by default.** Endpoint handlers are `async def` and reach
   the ORM via `aget` / `acreate` / `asave` / `adelete`. New endpoints
   should follow the same pattern.
5. **Imports come from `app.*`.** The Django app is named `app`. Do not
   rename it without also updating `app.settings`, `manage.py`,
   `conftest.py`, the AI manifest, and the test imports.
6. Keep `INSTALLED_APPS` minimal — `django.contrib.*` + `django_bolt` + `app`.

---

## 4. Version Management Rules

1. Use the current calendar date to reason about which Django, django-bolt,
   and msgspec versions are "current".
2. Prefer Long-Term Support / broadly adopted releases. When updating
   pinned versions in `requirements.txt`, also re-run
   `make test-gen-django-bolt` and `make test-django-bolt`.
3. **Do not fabricate version numbers.** If you cannot confirm the latest
   stable release, keep the existing pin and note the limitation in the
   commit message.
4. django-bolt is still pre-1.0. Avoid pulling in pre-release tags
   automatically — bump to a specific known-good version.

---

## 5. Testing Expectations

For non-trivial changes, run at least:

```bash
make clean-test
make test-generators
```

For changes scoped to this skeleton you may run only:

```bash
make test-gen-django-bolt
make test-django-bolt
```

Generated django-bolt test projects under `_test_projects/` should:

1. Successfully install dependencies via `./install-deps`.
2. Pass `python manage.py check`.
3. Pass the pytest suite via the wrapper `./test` script.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points (`gen`,
   `merge`, `test`, `test_skel`, `deps`, `install-deps`) without strong
   reason.
2. Do not hand-edit files that the AI manifest is set up to regenerate
   (`models.py`, `schemas.py`, `api.py`, `services/auth_service.py`,
   `tests/test_models.py`, `tests/test_api.py`). Fix the manifest prompt
   instead and re-run `_bin/skel-gen-ai python-django-bolt-skel ...`.
3. Do not introduce djangorestframework, simplejwt, drf-spectacular,
   django-filter, or any other DRF-ecosystem package. The skeleton's value
   is its django-bolt + msgspec stack.
4. Do not hard-code machine-specific paths or environment assumptions
   beyond what `deps` / `install-deps` already guarantee.
5. Do not modify `_test_projects/` by hand — regenerate via `gen` instead.
