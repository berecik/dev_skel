"""AI manifest for the ``python-fastapi-rag-skel`` skeleton.

The RAG skeleton inherits the DDD layout from ``python-fastapi-skel``
(``core/``, ``app/``) and adds RAG-specific modules (``app/rag/``,
``app/chat/``, ``app/documents/``).  This manifest tells ``skel-gen-ai``
to create a parallel CRUD module at ``app/{service_slug}/`` whose files
are AI-rewrites of the ``app/documents/`` templates, adapted to the
user's chosen service / item / authentication style.

The ``app/documents/`` module uses **Pydantic BaseModel** (not SQLModel)
for domain models and the same abstract repository / CRUD / UoW pattern
from ``core/``.

Placeholders are documented in ``_skels/_common/manifests/python-django-skel.py``.
"""

SYSTEM_PROMPT = """\
You are a senior FastAPI engineer regenerating one file inside the dev_skel
`{skeleton_name}` skeleton (a RAG-enabled FastAPI project).

Project layout:
- The FastAPI app package is `app/`. The on-disk service directory inside
  the wrapper `{project_name}/` is `{service_subdir}/` (= the slug of the
  user's `{service_label}`).
- Domain modules live in `app/<module>/` and follow a layered DDD style:
  `models.py` (Pydantic BaseModel + abstract repository/CRUD/UoW),
  `adapters/sql.py` (SQLModel concrete layer), `depts.py` (FastAPI
  dependency providers), `routes.py` (APIRouter endpoints).
- The existing `app/documents/` module is the reference pattern — it manages
  document metadata for the RAG pipeline.
- The new module being added is `app/{service_slug}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).

RAG-specific context:
- The skeleton ships `app/rag/` (embeddings, vector store, LLM chain,
  ingestion) and `app/chat/` (REST + WebSocket endpoints). These modules
  are NOT touched by this manifest — only the new CRUD module is generated.
- The RAG modules use ChromaDB for vector storage and LangChain for chain
  orchestration. The new CRUD module should NOT import from `app/rag/` or
  `app/chat/` unless the user explicitly requests it.

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
  exactly. The reference is the corresponding `app/documents/...` file.
- Replace every `Document` / `document` / `documents` token with the user's
  `{item_class}` / `{item_name}` / `{items_plural}` equivalents.
- Domain models use `pydantic.BaseModel` (NOT `sqlmodel.SQLModel`) — only
  the concrete adapter in `adapters/sql.py` uses SQLModel.
- Keep the imports relative (`from .models ...`, `from ..models ...`) the
  same way the reference does.
- Do NOT introduce new third-party dependencies. Reuse `core.deps.CurrentUser`
  exactly as the reference does when authentication is required.
- Do NOT import from `app.rag` or `app.chat` — the new module is a
  standalone CRUD entity.
- When `{auth_type}` is `none`, drop the `current_user` parameter and
  remove any owner-isolation checks from handlers.
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
            "template": "app/documents/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/__init__.py — module marker",
            "prompt": """\
Generate the `__init__.py` for the new `app/{service_slug}` module.

Mirror the REFERENCE exactly. If the reference is empty, output an empty
file (no content, no comments).

REFERENCE (`app/documents/__init__.py`):
---
{template}
---
""",
        },
        {
            "path": "app/{service_slug}/models.py",
            "template": "app/documents/models.py",
            "language": "python",
            "description": "app/{service_slug}/models.py — Pydantic BaseModel + abstract layer",
            "prompt": """\
Rewrite `app/documents/models.py` as `app/{service_slug}/models.py` for
a `{item_class}` entity.

Required transformations:
- Class names: `Document*` → `{item_class}*`. Keep the same suffixes
  (`Base`, `Create`, `Update`, `Repository`, `Crud`, `UnitOfWork`).
- The domain models use `pydantic.BaseModel` (NOT SQLModel). This is a
  key difference from the `python-fastapi-skel` — preserve it exactly.
- Add `title` (str) and `description` (Optional[str]) Pydantic fields on the
  base class. Drop any document-specific fields (`filename`, `content_type`,
  `file_size`, `chunk_count`, `status`) unless the user's entity logically
  needs them.
- Remove the `DocumentStatus` enum unless the user's entity warrants a
  status field — in that case rename it to `{item_class}Status`.
- Keep `core` imports identical to the reference:
  `from core import AbstractUnitOfWork, AbstractRepository, CRUDBase`.
- Match indentation and blank-line style of the REFERENCE.

REFERENCE (`app/documents/models.py`):
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
            "template": "app/documents/adapters/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/adapters/__init__.py — empty marker",
            "prompt": """\
Generate the `__init__.py` for the new `app/{service_slug}/adapters` package.

Mirror the REFERENCE exactly (likely empty).

REFERENCE (`app/documents/adapters/__init__.py`):
---
{template}
---
""",
        },
        {
            "path": "app/{service_slug}/adapters/sql.py",
            "template": "app/documents/adapters/sql.py",
            "language": "python",
            "description": "app/{service_slug}/adapters/sql.py — SQLModel concrete layer",
            "prompt": """\
Rewrite `app/documents/adapters/sql.py` as
`app/{service_slug}/adapters/sql.py`.

Required transformations:
- Class names: `Document*` → `{item_class}*` (incl. `SqlRepository`,
  `SqlUnitOfWork`).
- The SQLModel concrete class is named `{item_class}` and inherits from
  `{item_class}Base, SQLModel, table=True`. It must declare:
  `id: Optional[int] = Field(default=None, primary_key=True)` plus the
  fields from the base model as SQLModel `Field()` declarations.
- Drop document-specific fields (`filename`, `content_type`, `file_size`,
  `chunk_count`, `status`) and replace with the entity's own fields
  (`title`, `description`, etc.) as declared in `models.py`.
- The factory function is `get_{item_name}_uow`.
- Keep `core.adapters.sql` imports unchanged:
  `from core.adapters.sql import SqlAlchemyRepository, SqlAlchemyUnitOfWork`.
- Match indentation/style of the REFERENCE exactly.

REFERENCE (`app/documents/adapters/sql.py`):
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
            "template": "app/documents/depts.py",
            "language": "python",
            "description": "app/{service_slug}/depts.py — FastAPI dependency providers",
            "prompt": """\
Rewrite `app/documents/depts.py` as `app/{service_slug}/depts.py`.

Required transformations:
- Type aliases: `DocumentsUowDep` → `{item_class}sUowDep`,
  `DocumentsDep` → `{item_class}sDep`.
- Function: `get_documents_crud` → `get_{items_plural}_crud`.
- Imports: `.adapters.sql.get_document_uow` →
  `.adapters.sql.get_{item_name}_uow`; `DocumentUnitOfWork` →
  `{item_class}UnitOfWork`; `DocumentCrud` → `{item_class}Crud`.
- Match indentation/style of the REFERENCE exactly.

REFERENCE (`app/documents/depts.py`):
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
            "template": "app/documents/routes.py",
            "language": "python",
            "description": "app/{service_slug}/routes.py — FastAPI CRUD endpoints",
            "prompt": """\
Rewrite `app/documents/routes.py` as `app/{service_slug}/routes.py` for
the `{item_class}` entity.

Required transformations:
- Replace every `Document*` / `document*` / `documents` token with the
  corresponding `{item_class}*` / `{item_name}*` / `{items_plural}`
  equivalent.
- The dependency type is `{item_class}sDep` from `.depts` and the create /
  update Pydantic models are `{item_class}Create` / `{item_class}Update`.
- IMPORTANT: Remove all RAG-specific logic — file upload handling,
  `UploadFile`, `BackgroundTasks`, ingestion calls, vector store
  dependencies (`VectorStoreDep`, `RagSettingsDep`), and imports from
  `app.rag.*`. The new module is a plain CRUD entity.
- Replace the document upload endpoint (`POST /`) with a standard JSON
  create endpoint that accepts `{item_class}Create` in the request body.
- Keep standard CRUD routes: POST / (create), GET / (list),
  GET /{{id}} (get by id), DELETE /{{id}} (delete). Add PUT /{{id}}
  (update) using `{item_class}Update`.
- Authentication style for this service: `{auth_type}`.
  - When `{auth_type}` is `none`, do not import or use `CurrentUser`.
  - When `{auth_type}` is anything else, keep `CurrentUser` and
    owner-isolation checks as appropriate.
- Match indentation/style of the REFERENCE (minus RAG-specific parts).

REFERENCE (`app/documents/routes.py`):
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
            "template": "app/documents/__init__.py",
            "language": "python",
            "description": "app/{service_slug}/tests/__init__.py — empty marker",
            "prompt": """\
Generate `__init__.py` for the new `app/{service_slug}/tests` package.

Mirror the REFERENCE exactly (likely empty).

REFERENCE (`app/documents/__init__.py`):
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
# After the per-target MANIFEST above generates the new CRUD module,
# ``_bin/skel-gen-ai`` runs a SECOND Ollama pass against the block below.
# The integration phase has access to a snapshot of every sibling service
# in the wrapper via the ``{wrapper_snapshot}`` placeholder so the model
# can ground its rewrites in real code.
#
# Targets here are *additive* — they create new files (sibling clients,
# integration tests) without overwriting anything from the first phase.


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior FastAPI engineer integrating a freshly generated
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`python-fastapi-rag-skel`). It already ships:
- The wrapper-shared `wrapper_api` module with `Item`, `Category`,
  and `ReactState` models + routes mounted at `/api/items`,
  `/api/categories`, and `/api/state`.
- RAG-specific modules: `app/rag/` (embeddings, vector store, ingestion),
  `app/chat/` (REST + WebSocket chat endpoints), and `app/documents/`
  (document metadata CRUD).
- A user-chosen `{item_class}` module under `app/{service_slug}/`
  (models, adapters, depts, routes) with standard CRUD endpoints.
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
  `pyproject.toml`). Async tests are OK — mark them with
  `@pytest.mark.asyncio`.
- Read JWT material via `from core.config import JWT_SECRET,
  JWT_ALGORITHM` (the RAG skel exposes config values as module-level
  constants, not via a `settings` object).
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

4. `test_jwt_secret_is_wrapper_shared` — import `JWT_SECRET` from
   `core.config` and assert that
   `str(JWT_SECRET) == os.environ.get("JWT_SECRET", str(JWT_SECRET))`.

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
- `from core.config import JWT_SECRET`
- `from app.wrapper_api.db import Item, Category, ReactState, WrapperUser`
- (when {{sibling_count}} > 0) `from app.integrations.sibling_clients import IntegrationError, ...`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
