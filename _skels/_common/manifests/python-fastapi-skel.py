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
