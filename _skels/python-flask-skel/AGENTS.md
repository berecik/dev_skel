# Agents Rules for `python-flask-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`python-flask-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Flask-based backend skeleton.
- Lives at `_skels/python-flask-skel/`.
- Generates a minimal Flask application suitable for demos and small services.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`, etc.).
2. Keep Flask and core ecosystem packages reasonably up to date.
3. Ensure generated projects follow Flask best practices and remain easy to extend.

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
5. Core application files (e.g. under `_skels/python-flask-skel/app/`).

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Python and Flask)

Whenever you touch this skeleton, consider whether dependency versions should be updated.

1. Use the current calendar date to reason about which Python and Flask versions are "current".
2. Prefer the latest stable Python release that is widely supported by Flask and its ecosystem.
3. Prefer a stable, supported Flask release; read release notes before any major upgrade.
4. For pinned dependencies in `pyproject.toml` or installer scripts:
   - Prefer stable, widely used versions.
   - Watch for breaking changes in major upgrades.
5. Do not fabricate version numbers. If you cannot verify current versions, keep existing pins and
   document in commit messages that versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

---

## 4. Architecture and Style Constraints

1. Maintain a clear separation between app factory, configuration, routes, and models.
2. Follow standard Flask project layout conventions already present in the skeleton.
3. Avoid introducing non-standard patterns without updating documentation and tests.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at least:

```bash
make clean-test
make test-generators
```

Generated Flask test projects under `_test_projects/` should run and pass their tests using the
generated `./test` script.

If these expectations cannot be met, document the reason in the relevant docs file for this skeleton.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do not hard-code environment-specific paths or assumptions beyond what the `deps` script ensures.
3. Do not upgrade Flask or Python in a way that breaks generator tests without addressing the resulting issues.
