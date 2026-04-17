"""AI manifest for the ``python-flask-skel`` skeleton.

The flask skeleton already ships a working ``Item`` model and CRUD blueprint
under ``app/`` plus a pytest suite that exercises both. This manifest tells
``_bin/skel-gen-ai`` how to rewrite that ``Item``-shaped layer for the
user's ``{item_class}`` choice while preserving the wrapper-shared env
loading in ``app/config.py`` and the application factory in
``app/__init__.py``.
"""

SYSTEM_PROMPT = """\
You are a senior Flask engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Flask app package is `app/` (do NOT rename it). The on-disk service
  directory is `{service_subdir}/` inside the wrapper `{project_name}/`.
- The application factory lives in `app/__init__.py`. It exposes
  `db = SQLAlchemy()` and `migrate = Migrate()` and registers the
  `routes.bp` blueprint. Do NOT touch the factory unless a target
  explicitly says so.
- The reference entity is `Item` (table `items`). The user is replacing it
  with `{item_class}` (snake_case `{item_name}`, plural `{items_plural}`).
- The DB table for the new entity should be named `{items_plural}` so it
  collides cleanly with other backends in the same wrapper that use the
  same table name (the dev_skel shared-DB integration test relies on
  this).

Shared environment (CRITICAL — every backend service in the wrapper relies
on the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` — common database. Already wired in `app/config.py`'s
  `_resolve_database_url()` helper. DO NOT touch that helper or the
  wrapper-level `.env` loading block when regenerating any file.
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL` — shared JWT material exposed via the `Config` class.
  When you need to mint or verify a token, read them from `Config` (e.g.
  `current_app.config['JWT_SECRET']`).

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Use `flask`, `flask-sqlalchemy`, and (when needed) `pyjwt`. Do NOT
  introduce flask-restful, marshmallow, flask-jwt-extended, or any other
  package not already in the reference.
- Use `db.Model` from `app` for ORM definitions. Match the indentation,
  quoting, and import style of the REFERENCE template exactly.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `flask db migrate -m 'init {items_plural}'` and `flask db "
        "upgrade` after generation to materialise the new schema. The "
        "wrapper-shared `<wrapper>/_shared/db.sqlite3` file picks up the "
        "new table immediately."
    ),
    "targets": [
        {
            "path": "app/models.py",
            "template": "app/models.py",
            "language": "python",
            "description": "app/models.py — replace Item with {item_class}",
            "prompt": """\
Rewrite `app/models.py` to define a `{item_class}` model that maps to the
`{items_plural}` table.

- Class name: `{item_class}` (Title-case).
- `__tablename__ = "{items_plural}"`.
- Fields (mirror the REFERENCE Item, with the addition of an `is_completed`
  flag the integration test relies on):
  - `id` — `db.Integer`, primary key
  - `name` — `db.String(255)`, nullable=False
  - `description` — `db.String(1000)`, nullable=True
  - `is_completed` — `db.Boolean`, nullable=False, default=False
  - `created_at` — `db.DateTime`, default=`datetime.utcnow`
  - `updated_at` — `db.DateTime`, default=`datetime.utcnow`,
    onupdate=`datetime.utcnow`
- Provide a `to_dict()` method that includes every field (use
  `.isoformat()` for the datetimes).
- Imports must remain `from datetime import datetime` and `from app import db`.
- Match the indentation, quoting, and blank-line style of the REFERENCE.

REFERENCE (current `app/models.py`):
---
{template}
---
""",
        },
        {
            "path": "app/routes.py",
            "template": "app/routes.py",
            "language": "python",
            "description": "app/routes.py — CRUD blueprint for `{item_class}`",
            "prompt": """\
Rewrite `app/routes.py`. Keep the `index` and `health` endpoints from the
REFERENCE intact. Replace the existing `/api/items` endpoints with
`{item_class}`-specific equivalents:

- `GET /api/{items_plural}` → list every `{item_class}` (return a JSON
  list of `to_dict()` results).
- `POST /api/{items_plural}` → create a new `{item_class}` from the JSON
  body (`name` required, `description` and `is_completed` optional).
  Return 201 + the new row.
- `GET /api/{items_plural}/<int:item_id>` → fetch by id (404 when
  missing).
- `PATCH /api/{items_plural}/<int:item_id>/complete` → set
  `is_completed=True` and return the updated row.

Update the `from app.models import Item` line to import `{item_class}`,
and rename every `Item` reference accordingly.

Authentication style for this service: `{auth_type}`.
- `none`: no auth checks.
- `jwt` / `oauth` / `api_key`: at the top of the file add a tiny helper
  `_require_jwt()` that:
  1. Reads `Authorization: Bearer <token>` from `request.headers`.
  2. Decodes the token with `jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=[current_app.config['JWT_ALGORITHM']], issuer=current_app.config['JWT_ISSUER'])`.
  3. Aborts with 401 if anything fails.
  Call `_require_jwt()` at the top of every mutating endpoint
  (POST/PATCH/DELETE). Add `import jwt` and
  `from flask import current_app, abort, request` to the imports as
  needed. NEVER hardcode the secret — always pull it from
  `current_app.config`.
- `session` / `basic`: leave as `none` for now and add a one-line comment
  documenting that the user should bolt on Flask-Login or HTTP Basic.

Imports to keep: `from flask import Blueprint, jsonify, request`,
`from app import db`, plus whatever you add for the auth helper.

REFERENCE (current `app/routes.py`):
---
{template}
---
""",
        },
        {
            "path": "tests/test_routes.py",
            "template": "tests/test_routes.py",
            "language": "python",
            "description": "tests/test_routes.py — tests for `{item_class}` endpoints",
            "prompt": """\
Rewrite `tests/test_routes.py`. Keep the `app` and `client` fixtures and
the `test_index_returns_project_info` / `test_health_endpoint` tests
exactly as in the REFERENCE.

Replace `test_create_and_get_item` with the equivalent test for
`{item_class}`:

- `test_create_and_get_{item_name}`: POST to `/api/{items_plural}` with
  `name='Test {item_class}'`, assert 201 and the response includes the
  name; then GET `/api/{items_plural}/<id>` and assert it round-trips.
- `test_complete_{item_name}`: create a `{item_class}`, PATCH
  `/api/{items_plural}/<id>/complete`, assert the response has
  `is_completed=True`.

If `{auth_type}` is anything other than `none`, add a `pytest.mark.skip`
decorator with reason `"jwt-protected endpoints need a token; covered by
the integration test"` to the tests that hit POST/PATCH endpoints.

Imports must remain consistent with the REFERENCE.

REFERENCE (current `tests/test_routes.py`):
---
{template}
---
""",
        },
    ],
}


# --------------------------------------------------------------------------- #
#  Integration manifest (second Ollama session)
# --------------------------------------------------------------------------- #
#
# After the per-target MANIFEST above generates the new Flask service,
# ``_bin/skel-gen-ai`` runs a SECOND Ollama pass against the block below.
# The integration phase has access to a snapshot of every sibling service
# in the wrapper via the ``{wrapper_snapshot}`` placeholder so the model
# can ground its rewrites in real code.
#
# Targets here are *additive* — they create new files (sibling clients,
# integration tests) without overwriting anything from the first phase.
# Each target's prompt receives the same template variables as the main
# MANIFEST plus:
#
#   - ``{wrapper_snapshot}`` — Markdown rendering of every sibling
#     service (slug, kind, tech, key files).
#   - ``{sibling_count}`` — number of siblings discovered.
#   - ``{sibling_slugs}`` — comma-separated list of sibling slugs (or
#     ``"(none)"`` when the new service is the only one in the wrapper).
#
# After the integration files are written, the test-and-fix loop runs
# the ``test_command`` (defaults to ``./test`` so the wrapper-shared
# dispatch script picks pytest). On failure, it asks Ollama to repair
# each integration file in turn, capped at ``fix_timeout_m`` minutes.


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Flask engineer integrating a freshly generated service
into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`python-flask-skel`). It already ships:
- The wrapper-shared `Item`, `Category`, and `ReactState` models
  (defined in `app/models.py`, SQLAlchemy via `db.Model`) plus Flask
  blueprint routes for `/api/items`, `/api/categories`, and
  `/api/state`.
- A user-chosen `{item_class}` entity — the per-target manifest
  rewrote the `Item`-shaped CRUD layer for `{item_class}` in
  `app/models.py` and `app/routes.py`.
- JWT auth via PyJWT through the `@jwt_required` decorator defined in
  `app/auth.py`, signed with `current_app.config['JWT_SECRET']` (the
  wrapper-shared secret — NEVER hardcode it).
- The wrapper-shared `<wrapper>/.env` is loaded by `app/config.py`
  before the local `.env` so `DATABASE_URL` and the JWT vars are
  identical to every other backend in the project.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Python client for each sibling backend the new service
   should call. The client must read the sibling's URL from
   `os.environ["SERVICE_URL_<UPPER_SLUG>"]` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Pytest integration tests that exercise the cross-service flows
   end-to-end via the wrapper-shared SQLite database (and, when
   sibling backends are present, via the typed clients above).

Coding rules:
- Use **Flask** + **SQLAlchemy** + **PyJWT** — the same libraries
  the wrapper-shared routes already use. Do NOT introduce DRF,
  FastAPI, django-bolt, marshmallow, flask-restful, or any other
  framework.
- Use `pytest` with the Flask test client (already pinned in
  `requirements.txt`). All tests MUST be synchronous (plain `def`,
  NOT `async def`).
- Read JWT material via `current_app.config['JWT_SECRET']` (or
  `app.config['JWT_SECRET']` when you have the app fixture). NEVER
  hardcode the secret.
- Read `DATABASE_URL` indirectly via the existing
  `_resolve_database_url()` helper in `app/config.py` — do NOT touch
  `config.py` from these prompts.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items`, `/api/state`, and
  `/api/{items_plural}` endpoints via the ORM or test client. Do not
  assume sibling services exist; gracefully degrade.

User-supplied integration instructions (free-form, take with the same
weight as the rules above):
{integration_extra}

User-supplied backend instructions (already applied during the
per-target phase, repeated here so the integration code stays
consistent):
{backend_extra}
"""


INTEGRATION_MANIFEST = {
    "system_prompt": INTEGRATION_SYSTEM_PROMPT,
    "notes": (
        "Integration phase: writes app/integrations/sibling_clients.py "
        "and tests/test_integration.py, then runs the test-and-fix "
        "loop via `./test tests/test_integration.py`."
    ),
    # The wrapper-shared `./test` script runs pytest with the project's
    # virtualenv already activated. Restricting to the integration test
    # file keeps the loop tight (~3 s per iteration) instead of running
    # the entire suite on every fix attempt.
    "test_command": "./test tests/test_integration.py -q --maxfail=3",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "app/integrations/__init__.py",
            "language": "python",
            "description": "app/integrations/__init__.py — package marker",
            "prompt": """\
Create the `app/integrations/__init__.py` package marker. Empty file
is fine, but include a one-line module docstring describing what
lives under this package:

\"\"\"Cross-service clients used by the {service_label} integration tests.\"\"\"
""",
        },
        {
            "path": "app/integrations/sibling_clients.py",
            "language": "python",
            "description": "app/integrations/sibling_clients.py — typed clients for sibling backends",
            "prompt": """\
Write `app/integrations/sibling_clients.py`. The module exposes one
typed client class per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Use `urllib.request` and `json` from the stdlib (do NOT add an
  `httpx` / `requests` dependency — keep the Flask service
  dependency-light).
- Each sibling backend gets a class named `<PascalSlug>Client`
  (e.g. `WebUiClient`, `AuthApiClient`). The class:
    - Reads its base URL from `os.environ["SERVICE_URL_<UPPER_SLUG>"]`
      in `__init__`. Raise `RuntimeError` with a clear message when
      the env var is missing.
    - Accepts an optional `token: str | None` parameter; when set,
      every request sends `Authorization: Bearer <token>`.
    - Exposes `list_items()` and `get_state(key: str)` sync methods
      that hit the sibling's wrapper-shared `/api/items` and
      `/api/state/{{key}}` endpoints. Return parsed JSON dicts.
    - Raises `IntegrationError` (define it at the top of the file)
      on non-2xx responses, with the status code and response body.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationError` class and a single
  `__all__ = ["IntegrationError"]` export. Do NOT define dummy client
  classes for non-existent siblings.
- Type-annotate every public function. Use `from __future__ import
  annotations` so forward references are cheap.
- Use 4-space indentation, double-quoted strings, and PEP-8 import
  ordering.

Output the full file contents only.
""",
        },
        {
            "path": "tests/test_integration.py",
            "language": "python",
            "description": "tests/test_integration.py — cross-service pytest cases",
            "prompt": """\
Write `tests/test_integration.py`. Pytest integration tests that
exercise the new `{service_label}` service end-to-end and (when sibling
backends are present) verify the cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- All tests MUST be **synchronous** (plain `def`, NOT `async def`).
  Do NOT use `@pytest.mark.asyncio`.
- The wrapper-shared `Item`, `Category`, `ReactState`, and `User`
  models are defined in `app/models.py` (SQLAlchemy `db.Model`).
- `ReactState.value` is a `Text` column — it stores opaque strings,
  NOT native Python dicts.
- Use the Flask test client for HTTP-level tests and the SQLAlchemy
  `db.session` for ORM-level tests. The `app` and `client` fixtures
  from `conftest.py` provide the app context.
- When testing sibling clients, the `SERVICE_URL_<SLUG>` env var
  may not be set (e.g. in CI or when the sibling isn't running).
  Always guard client instantiation with `try/except` and call
  `pytest.skip()` when the env var is missing or the service is
  unreachable.

Required tests:

1. `test_items_endpoint_round_trip` — within an app context, create
   an `Item` via `db.session.add(Item(name=..., description=...))`,
   commit, then query it back via `db.session.query(Item).first()`
   and assert it round-trips.

2. `test_react_state_round_trip` — create a `User` row, then create
   a `ReactState` row with `key="test_key"` and `value="some_data"`,
   commit, read it back, and assert `state.value == "some_data"`.

3. `test_{items_plural}_endpoint_uses_jwt` — import
   `mint_access_token` from `app.auth`, create a `User` row, mint
   a token via `mint_access_token(user.id)`, and assert the result
   is a non-empty string.

4. `test_jwt_secret_is_wrapper_shared` — within an app context,
   assert that
   `app.config['JWT_SECRET'] == os.environ.get("JWT_SECRET", app.config['JWT_SECRET'])`.

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `test_sibling_<slug>_items_visible_via_shared_db`.
   Guard instantiation like this:
   ```python
   try:
       client = SomeClient()
   except (RuntimeError, IntegrationError):
       pytest.skip("SERVICE_URL_<SLUG> not set")
   ```
   Then call `client.list_items()` inside `try/except` and
   `pytest.skip` if unreachable.

6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Imports:
- `import os, pytest`
- `from app import create_app, db`
- `from app.models import Item, Category, ReactState, User`
- `from app.auth import mint_access_token`
- (when {sibling_count} > 0) `from app.integrations.sibling_clients import IntegrationError, ...`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
