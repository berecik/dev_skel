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
