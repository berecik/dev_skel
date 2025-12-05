# Junie Rules for `python-flask-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`python-flask-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Flask-based backend skeleton.
- Lives at `_skels/python-flask-skel/`.
- Generates small Flask apps for demos and APIs.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Flask and core ecosystem packages reasonably up to date.
3. Ensure generated projects remain simple and idiomatic for Flask.

---

## 2. Files to Check First

When working on `python-flask-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/python-flask-skel.md` (if present).
2. Skeleton Makefile: `_skels/python-flask-skel/Makefile`.
3. Generator scripts:
   - `_skels/python-flask-skel/gen`
   - `_skels/python-flask-skel/merge`
   - `_skels/python-flask-skel/test_skel`
4. Dependency installers:
   - `_skels/python-flask-skel/deps`
   - `_skels/python-flask-skel/install-deps`
5. Core application code under `_skels/python-flask-skel/app/`.

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Python and Flask)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the **current calendar date** to reason about which Python and Flask
   versions are "current".
2. Prefer the latest stable Python version compatible with Flask and the
   ecosystem, respecting any global minimum in `_docs/DEPENDENCIES.md`.
3. Prefer stable, well-supported Flask releases and review release notes
   before major upgrades.
4. For dependencies in `pyproject.toml` or installer scripts, prefer stable
   versions and watch for breaking changes in extensions (e.g. SQLAlchemy or
   similar integrations if used).
5. Do **not** fabricate version numbers. If you cannot confirm current
   versions, keep existing pins and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

If you change behaviour specific to Flask, also run any available
Flask-specific tests (for example via
`cd _skels/python-flask-skel && make test`).

---

## 4. Architecture and Style Constraints

1. Follow idiomatic Flask patterns: create an app instance, define routes in
   dedicated modules, and keep configuration manageable.
2. Keep example routes minimal but realistic, mirroring existing patterns in
   `app/routes.py` and tests.
3. Avoid introducing heavy frameworks or patterns that do not match Flask’s
   typical usage without updating docs and tests.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

Generated Flask test projects under `_test_projects/` should:

1. Start successfully using the generated run script.
2. Pass their tests using the generated `./test` script.

If these expectations cannot be met, document the reason in the relevant
docs file for this skeleton.

---

## 6. Do Not

1. Do **not** remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do **not** hard-code environment-specific paths or assumptions beyond what
   the `deps` script guarantees.
3. Do **not** upgrade Flask or Python in a way that breaks generator tests
   without addressing resulting issues.
