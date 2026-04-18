# Agents Rules for `python-django-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`python-django-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.


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

- Provides a Django-based backend skeleton.
- Lives at `_skels/python-django-skel/`.
- Uses `django-admin startproject` (see docs and scripts) and overlays
  additional files via `merge`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Django and core ecosystem packages reasonably up to date.
3. Ensure generated projects follow Django best practices and remain easy to
   extend.

---

## 2. Files to Check First

When working on `python-django-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/python-django-skel.md` (if present).
2. Skeleton Makefile: `_skels/python-django-skel/Makefile`.
3. Generator scripts:
   - `_skels/python-django-skel/gen`
   - `_skels/python-django-skel/merge`
   - `_skels/python-django-skel/test_skel`
4. Dependency installers:
   - `_skels/python-django-skel/deps`
   - `_skels/python-django-skel/install-deps`
5. Project template code (for example under
   `_skels/python-django-skel/myproject/`).

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Python and Django)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the current calendar date to reason about which Python and Django
   versions are "current".
2. Prefer the latest stable Python release that is widely supported by
   Django and its ecosystem, respecting any global minimum version defined in
   `_docs/DEPENDENCIES.md`.
3. Prefer a stable, supported Django release; read release notes before any
   major upgrade.
4. For pinned dependencies in `pyproject.toml` or installer scripts:
   - Prefer stable, widely used versions.
   - Watch for breaking changes (e.g. Django LTS → next major).
5. Do not fabricate version numbers. If you cannot verify current
   versions, keep existing pins and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

If you change behaviour specific to Django, also run the skeleton-specific
tests if available (e.g. via `cd _skels/python-django-skel && make test`).

---

## 4. Architecture and Style Constraints

1. Maintain a clear separation between settings, URLs, views, and models.
2. Follow standard Django project layout conventions and patterns already
   present in the skeleton.
3. Avoid introducing non-standard patterns (e.g. heavy custom frameworks)
   without updating documentation and tests.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

Generated Django test projects under `_test_projects/` should:

1. Apply migrations successfully.
2. Run their tests using the generated `./test` script.

If these expectations cannot be met, document the reason in the relevant
docs file for this skeleton.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do not hard-code environment-specific paths or assumptions about
   installed tools beyond what the `deps` script ensures.
3. Do not upgrade Django or Python in a way that breaks generator tests
   without addressing the resulting issues.
