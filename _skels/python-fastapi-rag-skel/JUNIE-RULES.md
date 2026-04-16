# Junie Rules for `python-fastapi-rag-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`python-fastapi-rag-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a FastAPI-based backend skeleton using **async SQLAlchemy** and a
  layered DDD-style structure.
- Lives at `_skels/python-fastapi-rag-skel/`.
- Generates test projects like `_test_projects/test-fastapi-app` and
  `_test_projects/test-fastapi-ddd-app`.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep FastAPI and its core ecosystem reasonably up to date.
3. Ensure generated projects are production-capable but simple to
   understand.

---

## 2. Files to Check First

When working on `python-fastapi-rag-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/python-fastapi-rag-skel.md`
2. Skeleton Makefile: `_skels/python-fastapi-rag-skel/Makefile`
3. Generator scripts:
   - `_skels/python-fastapi-rag-skel/gen`
   - `_skels/python-fastapi-rag-skel/merge`
   - `_skels/python-fastapi-rag-skel/test_skel`
4. Dependency installers:
   - `_skels/python-fastapi-rag-skel/deps`
   - `_skels/python-fastapi-rag-skel/install-deps`
5. Core application code (may evolve over time, but typically under
   `_skels/python-fastapi-rag-skel/app/` or `core/`).
6. Test projects for behaviour reference:
   - `_test_projects/test-fastapi-app/`
   - `_test_projects/test-fastapi-ddd-app/`

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (FastAPI, Python, and Core Libraries)

Whenever you touch this skeleton, you must consider whether dependency
versions should be updated.

### 3.1 Sources of Truth

1. Use the **current calendar date** (provided by the system) to reason about
   which versions are "current".
2. Check the latest **stable** release versions of at least:
   - Python (CPython)
   - FastAPI
   - Uvicorn
   - SQLAlchemy
   - Pydantic and `pydantic-settings` (or their modern equivalents)
   - HTTPX / testing libraries used here
3. Prefer Long-Term Support (LTS) or broadly adopted stable releases over
   very fresh, experimental releases.

You must not fabricate specific version numbers. If you cannot reliably
obtain the latest version numbers (for example, because external network
access is unavailable), you must:

1. Keep the existing pinned versions.
2. Clearly document in commit messages and comments that versions were not
   updated due to unavailable information.

### 3.2 Python Version Policy

- Prefer the **latest stable Python release** that is commonly supported by
  FastAPI and the key ecosystem libraries.
- When the global documentation (`_docs/DEPENDENCIES.md`) specifies a
  minimum Python version, follow that; otherwise, prefer `python >= 3.11`
  or higher when safely supported.
- When updating the Python version, you must:
  1. Update `pyproject.toml` and any runtime images (e.g. Dockerfile) in this
     skeleton.
  2. Update any CI configuration within this skeleton if present.
  3. Regenerate and run the FastAPI test projects.

### 3.3 FastAPI and Core Dependencies Policy

- Periodically (or whenever the user requests dependency updates), you
  should:
  1. Check for new stable releases of FastAPI and key dependencies.
  2. Update pinned versions in this skeleton (typically in `pyproject.toml`
     and/or dependency installer scripts).
  3. Run:
     - `make clean-test`
     - `make test-generators`
     - And, if available, the skeleton-specific tests (e.g.
       `cd _skels/python-fastapi-rag-skel && make test`).

- When updating versions, pay special attention to:
  - Deprecation warnings from FastAPI, Starlette, Pydantic, SQLAlchemy.
  - Changes in default behaviour (e.g. Pydantic v1 vs v2 differences).
  - Any need to adjust `config.py`, models, routers, or test setup.

If an upgrade introduces breaking changes you cannot fix quickly, you may
decide to **stay on the previous stable release**, but you must:

1. Document the reason in `_docs/python-fastapi-rag-skel.md` ("Known
   limitations" or similar section).
2. Optionally add a note in this `JUNIE-RULES.md` file explaining why the
   skeleton is pinned.

---

## 4. Architecture and Style Constraints

1. Maintain a clear separation between:
   - Configuration and settings (e.g. `config.py` or similar modules).
   - Database models and migrations (SQLAlchemy, Alembic).
   - API routers and request/response models.
   - Background tasks or domain services.
2. Prefer async endpoints and async DB access when possible.
3. Follow existing logging patterns (see `core/common_logging.py` and
   `core/logging.py` where present).
4. Keep example routes and models minimal but realistic; avoid over-complex
   demo logic.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

If you change behaviour that is specific to `python-fastapi-rag-skel`, also run:

```bash
cd _skels/python-fastapi-rag-skel
make test
```

Generated FastAPI test projects under `_test_projects/` should:

1. Start successfully using the provided `./run` scripts.
2. Pass their tests using `./test`.

If any of these expectations cannot be met, document the reason in
`_docs/python-fastapi-rag-skel.md` and, if relevant, in this file.

---

## 6. Do Not

1. Do **not** remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do **not** hard-code machine-specific paths or environment assumptions.
3. Do **not** introduce experimental FastAPI features that are unstable or
   tied to very recent pre-releases unless the user explicitly asks.
