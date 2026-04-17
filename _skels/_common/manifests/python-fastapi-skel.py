"""AI manifest for the ``python-fastapi-skel`` skeleton.

The fastapi skeleton already ships with a complete reference module under
``app/example_items/`` (models, adapters, routes, deps). This manifest tells
``skel-gen-ai`` to create a parallel module ``app/{service_slug}/`` whose
files are AI-rewrites of the example_items templates, adapted to the user's
chosen service / item / authentication style.

Placeholders are documented in ``_skels/_common/manifests/python-django-skel.py``.
"""

SYSTEM_PROMPT = """\
You are a senior FastAPI engineer regenerating one file inside the dev_skel
`{skeleton_name}` skeleton.

Project layout:
- The FastAPI app package is `app/`. The on-disk service directory inside
  the wrapper `{project_name}/` is `{service_subdir}/` (= the slug of the
  user's `{service_label}`).
- Domain modules live in `app/<module>/` and follow a layered DDD style:
  `models.py` (Pydantic + abstract repository/CRUD/UoW), `adapters/sql.py`
  (SQLModel + concrete UoW), `depts.py` (FastAPI dependency providers),
  `routes.py` (APIRouter endpoints).
- The new module being added is `app/{service_slug}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).

Shared environment (CRITICAL — every backend service in the wrapper relies
on the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` — common database. Already wired in `core/config.py`.
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL` — shared JWT material. When you need them inside a
  generated module, import them from `core.config` (not `core.security`'s
  old hardcoded constants). The reference `core.deps.CurrentUser` already
  delegates to that flow.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match the indentation, quoting, and import style of the REFERENCE template
  exactly. The reference is the corresponding `app/example_items/...` file.
- Replace every `ExampleItem` / `example_item` / `example_items` token with
  the user's `{item_class}` / `{item_name}` / `{items_plural}` equivalents.
- Keep the imports relative (`from .models ...`, `from ..models ...`) the
  same way the reference does.
- Do NOT introduce new third-party dependencies. Reuse `core.deps.CurrentUser`
  exactly as the reference does when authentication is required.
- When `{auth_type}` is `none`, drop the `current_user` parameter and
  remove the owner-isolation checks from list/get/update/delete handlers.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "After generation, register the new module by adding "
        "`router.include_router({service_slug}_routes.router, "
        "tags=['{items_plural}'], prefix='/{items_plural}')` in `app/routes.py`."
    ),
    "targets": [
        {
            "path": "app/{service_slug}/__init__.py",
            "template": "app/example_items/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/__init__.py — module marker",
            "prompt": """\
Generate the `__init__.py` for the new `app/{service_slug}` module.

Mirror the REFERENCE exactly. If the reference is empty, output an empty
file (no content, no comments).

REFERENCE (`app/example_items/__init__.py`):
---
{template}
---
""",
        },
        {
            "path": "app/{service_slug}/models.py",
            "template": "app/example_items/models.py",
            "language": "python",
            "description": "app/{service_slug}/models.py — pydantic + abstract layer",
            "prompt": """\
Rewrite `app/example_items/models.py` as `app/{service_slug}/models.py` for
a `{item_class}` entity.

Required transformations:
- Class names: `ExampleItem*` → `{item_class}*`. Keep the same suffixes
  (`Base`, `Create`, `Update`, `Repository`, `Crud`, `UnitOfWork`).
- Add `title` (str) and `description` (Optional[str]) Pydantic fields on the
  base class. Keep `owner_id: Optional[int] = None` only when `{auth_type}`
  is not `none`; otherwise drop it entirely along with the
  `filter_by_owner` / `get_by_owner` helpers.
- Keep `core` imports identical to the reference.
- Match indentation and blank-line style of the REFERENCE.

REFERENCE (`app/example_items/models.py`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "app/{service_slug}/adapters/__init__.py",
            "template": "app/example_items/adapters/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/adapters/__init__.py — empty marker",
            "prompt": """\
Generate the `__init__.py` for the new `app/{service_slug}/adapters` package.

Mirror the REFERENCE exactly (likely empty).

REFERENCE (`app/example_items/adapters/__init__.py`):
---
{template}
---
""",
        },
        {
            "path": "app/{service_slug}/adapters/sql.py",
            "template": "app/example_items/adapters/sql.py",
            "language": "python",
            "description": "app/{service_slug}/adapters/sql.py — SQLModel concrete layer",
            "prompt": """\
Rewrite `app/example_items/adapters/sql.py` as
`app/{service_slug}/adapters/sql.py`.

Required transformations:
- Class names: `ExampleItem*` → `{item_class}*` (incl. `SqlRepository`,
  `SqlUnitOfWork`).
- The SQLModel concrete class is named `{item_class}` and inherits from
  `{item_class}Base, SQLModel, table=True`. It must declare:
  `id: Optional[int] = Field(default=None, primary_key=True)` and, when
  `{auth_type}` is not `none`,
  `owner_id: Optional[int] = Field(default=None, foreign_key='user.id')`.
- The factory function is `get_{item_name}_uow`.
- When `{auth_type}` is `none`, remove the `filter_by_owner` method.
- Keep `core.adapters.sql` imports unchanged.
- Match indentation/style of the REFERENCE exactly.

REFERENCE (`app/example_items/adapters/sql.py`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "app/{service_slug}/depts.py",
            "template": "app/example_items/depts.py",
            "language": "python",
            "description": "app/{service_slug}/depts.py — FastAPI dependency providers",
            "prompt": """\
Rewrite `app/example_items/depts.py` as `app/{service_slug}/depts.py`.

Required transformations:
- Type aliases: `ExampleItemsUowDep` → `{item_class}sUowDep`,
  `ExampleItemsDep` → `{item_class}sDep`.
- Function: `get_example_items_crud` → `get_{items_plural}_crud`.
- Imports: `.adapters.sql.get_example_item_uow` →
  `.adapters.sql.get_{item_name}_uow`; `ExampleItemUnitOfWork` →
  `{item_class}UnitOfWork`; `ExampleItemCrud` → `{item_class}Crud`.
- Match indentation/style of the REFERENCE exactly.

REFERENCE (`app/example_items/depts.py`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "app/{service_slug}/routes.py",
            "template": "app/example_items/routes.py",
            "language": "python",
            "description": "app/{service_slug}/routes.py — FastAPI endpoints",
            "prompt": """\
Rewrite `app/example_items/routes.py` as `app/{service_slug}/routes.py` for
the `{item_class}` entity.

Required transformations:
- Replace every `ExampleItem*` / `example_item*` / `example_items` token
  with the corresponding `{item_class}*` / `{item_name}*` / `{items_plural}`
  equivalent.
- The dependency type is `{item_class}sDep` from `.depts` and the create /
  update Pydantic models are `{item_class}Create` / `{item_class}Update`.
- Authentication style for this service: `{auth_type}`.
  - When `{auth_type}` is `none`, remove the `current_user: CurrentUser`
    parameter from every handler and drop all
    `current_user.is_superuser` / owner-isolation checks. The list endpoint
    just returns `{items_plural}.list()`.
  - When `{auth_type}` is anything else, keep `CurrentUser` and the existing
    superuser/owner checks unchanged.
- The endpoint paths and HTTP methods stay the same as the REFERENCE.
- Match indentation/style of the REFERENCE exactly.

REFERENCE (`app/example_items/routes.py`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "app/{service_slug}/tests/__init__.py",
            "template": "app/example_items/tests/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/tests/__init__.py — empty marker",
            "prompt": """\
Generate `__init__.py` for the new `app/{service_slug}/tests` package.

Mirror the REFERENCE exactly (likely empty).

REFERENCE (`app/example_items/tests/__init__.py`):
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
# After the per-target MANIFEST above generates the new FastAPI service,
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
You are a senior FastAPI engineer integrating a freshly generated
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`python-fastapi-skel`). It already ships:
- The wrapper-shared `wrapper_api` module with `Item`, `Category`,
  and `ReactState` models + routes mounted at `/api/items`,
  `/api/categories`, and `/api/state`.
- A user-chosen `{item_class}` module under `app/{service_slug}/`
  (models, adapters, depts, routes) with async endpoints.
- JWT auth via `jose` (python-jose) through `core.security` +
  `core.deps.CurrentUser`, signed with `config.JWT_SECRET` (the
  wrapper-shared secret read from `core.config`).
- The wrapper-shared `<wrapper>/.env` is loaded by `core/config.py`
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
- Use **FastAPI** + **SQLModel** + **python-jose** — the same
  libraries the wrapper-shared API already uses. Do NOT introduce
  DRF, Flask, django-bolt, or any other framework.
- Use `pytest` + `pytest-asyncio` (already pinned in
  `requirements.txt`). Async tests are OK — mark them with
  `@pytest.mark.asyncio`.
- Read JWT material via `from core.config import settings` and
  reference `settings.JWT_SECRET`, `settings.JWT_ALGORITHM`, etc.
- Read `DATABASE_URL` indirectly via the existing `core/config.py`
  settings — do NOT touch `core/config.py` from these prompts.
- For sibling HTTP calls prefer `httpx` (already a dependency for
  FastAPI test client) or fall back to `urllib.request`. Do NOT add
  `requests` as a new dependency.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items`, `/api/state`, and
  `/{items_plural}` endpoints via the ORM or test client. Do not
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
        "and app/tests/test_integration.py, then runs the test-and-fix "
        "loop via `./test app/tests/test_integration.py`."
    ),
    # The wrapper-shared `./test` script runs pytest with the project's
    # virtualenv already activated. Restricting to the integration test
    # file keeps the loop tight (~3 s per iteration) instead of running
    # the entire suite on every fix attempt.
    "test_command": "./test app/tests/test_integration.py -q --maxfail=3",
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

- Use `httpx` (already a FastAPI test dependency) for HTTP calls, or
  fall back to `urllib.request` + `json` from the stdlib. Do NOT add
  `requests` as a new dependency.
- Each sibling backend gets a class named `<PascalSlug>Client`
  (e.g. `WebUiClient`, `AuthApiClient`). The class:
    - Reads its base URL from `os.environ["SERVICE_URL_<UPPER_SLUG>"]`
      in `__init__`. Raise `RuntimeError` with a clear message when
      the env var is missing.
    - Accepts an optional `token: str | None` parameter; when set,
      every request sends `Authorization: Bearer <token>`.
    - Exposes `list_items()` and `get_state(key: str)` methods (async
      or sync) that hit the sibling's wrapper-shared `/api/items` and
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
            "path": "app/tests/test_integration.py",
            "language": "python",
            "description": "app/tests/test_integration.py — cross-service pytest cases",
            "prompt": """\
Write `app/tests/test_integration.py`. Pytest integration tests that
exercise the new `{service_label}` service end-to-end and (when sibling
backends are present) verify the cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Tests may be async (`async def` + `@pytest.mark.asyncio`) or
  synchronous — either is acceptable for this FastAPI skeleton.
- The wrapper-shared `Item`, `Category`, and `ReactState` SQLModel
  tables are defined in `app/wrapper_api/db.py`. Import them from
  there: `from app.wrapper_api.db import Item, Category, ReactState,
  WrapperUser`.
- `ReactState.value` is a `Text` column — it stores opaque strings,
  NOT native Python dicts.
- When testing sibling clients, the `SERVICE_URL_<SLUG>` env var
  may not be set (e.g. in CI or when the sibling isn't running).
  Always guard client instantiation with `try/except` and call
  `pytest.skip()` when the env var is missing or the service is
  unreachable.

Required tests:

1. `test_items_endpoint_round_trip` — using a SQLModel `Session`
   (from `app/wrapper_api/db.get_session`), create an `Item` row,
   commit, then query it back and assert it round-trips.

2. `test_react_state_round_trip` — create a `WrapperUser`, then
   create a `ReactState` row with `key="test_key"` and
   `value="some_data"`, read it back, and assert
   `state.value == "some_data"`.

3. `test_{items_plural}_endpoint_uses_jwt` — import `create_token`
   from `core.security` (or the wrapper_api security module), mint
   a token for a test user, and assert the result is a non-empty
   string.

4. `test_jwt_secret_is_wrapper_shared` — import settings from
   `core.config` and assert that
   `settings.JWT_SECRET == os.environ.get("JWT_SECRET", settings.JWT_SECRET)`.

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
- `from core.config import settings`
- `from app.wrapper_api.db import Item, Category, ReactState, WrapperUser`
- (when {sibling_count} > 0) `from app.integrations.sibling_clients import IntegrationError, ...`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
