"""AI manifest for the ``python-django-bolt-skel`` skeleton.

This manifest tells ``_bin/skel-gen-ai`` how to rewrite the canonical
django-bolt service files for a user-supplied entity. Unlike the plain
``python-django-skel`` manifest (which creates a brand-new app), this one
edits the files **in place** under the existing ``app/`` package because the
django-bolt layout assumes a single ``app`` package by convention.

The skeleton already ships with a working `Project → Task` reference. The
prompts ask Ollama to swap the `Task` entity for the user's
`{item_class}` while keeping `User`, `UserProfile`, and `Project`
unchanged so the auth + ownership flows continue to work out of the box.
"""

SYSTEM_PROMPT = """\
You are a senior django-bolt engineer regenerating one source file inside
the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Django app is named `app/` (do NOT rename it). The on-disk service
  directory is `{service_subdir}/` inside the wrapper `{project_name}/`.
- `app.urls.urlpatterns` is intentionally empty — every endpoint lives on
  the `BoltAPI()` instance in `app/api.py` via decorators.
- The skeleton's existing reference entity is `Task`. The user is replacing
  it with `{item_class}` (snake_case `{item_name}`, plural `{items_plural}`).
- `User`, `UserProfile`, `Project`, **`Item`**, and **`ReactState`** already
  exist and must remain unchanged. Only the `Task`-shaped layer (model +
  schema + viewset + service helpers + tests) is rewritten.
  - `Item` (table `items`) is the wrapper-shared CRUD resource the React
    skeleton consumes via `${{BACKEND_URL}}/api/items` — touching it would
    break the cross-stack contract.
  - `ReactState` (table `react_state`) backs the `/api/state` save/load
    endpoints that the React state-management layer relies on. Same
    rule: KEEP THE MODEL, THE SCHEMAS, AND THE HANDLERS VERBATIM.

Shared environment (CRITICAL — all backend services in the wrapper rely
on the same env vars from `<wrapper>/.env`):
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL` — used everywhere a token is minted or verified. Read
  them via `from django.conf import settings` and reference
  `settings.JWT_SECRET` etc. NEVER use `settings.SECRET_KEY` for token
  signing — it is a Django-specific salt that may differ between services.
- `DATABASE_URL` — every backend service points at the same database via
  this env var. The skeleton's settings.py already wires the resolution
  logic; do NOT touch settings.py from these prompts.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Use django-bolt for the API: `BoltAPI`, `ModelViewSet`, `@action`,
  `JSON`, `Request`, `PageNumberPagination`, `JWTAuthentication`,
  `IsAuthenticated`, `AllowAny`, `get_current_user`,
  `create_jwt_for_user`, `Token`. Do NOT introduce djangorestframework,
  simplejwt, or any other DRF-ecosystem package.
- Use `msgspec.Struct` for all schemas (NOT DRF serializers, NOT pydantic).
- Use the async ORM (`aget`, `acreate`, `asave`, `adelete`); endpoints are
  `async def`.
- Use `from django.contrib.auth.models import User` directly, never
  `get_user_model()`.
- Match the indentation, quoting, and import style of the REFERENCE
  template exactly.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `python manage.py makemigrations app && python manage.py migrate` "
        "after generation. The skeleton ships `--nomigrations` in its pytest "
        "config so the test suite still passes before you create real "
        "migrations."
    ),
    "targets": [
        {
            "path": "app/models.py",
            "template": "app/models.py",
            "language": "python",
            "description": "app/models.py — replace Task with {item_class}",
            "prompt": """\
Rewrite `app/models.py`. Keep `UserProfile`, `Project`, the
`create_user_profile` post_save signal, **`Item`**, and **`ReactState`**
EXACTLY as in the REFERENCE — they back the wrapper-shared
`/api/items` and `/api/state` endpoints that the React frontend
consumes, and removing them would break the cross-stack contract.

Replace the `Task` model with a `{item_class}` model that:

- Has the same fields as `Task`: `title`, `description`, `project`,
  `assignee`, `priority` (TextChoices), `status` (TextChoices),
  `is_completed`, `created_at`, `updated_at`.
- Uses `related_name='{items_plural}'` on the `project` ForeignKey and
  `related_name='assigned_{items_plural}'` on the `assignee` ForeignKey.
- Has `class Meta: ordering = ['-created_at']` and `__str__` returning
  `self.title`.
- Keeps the inner `Priority` and `Status` TextChoices classes verbatim.

Imports must stay identical to the REFERENCE.

REFERENCE (current `app/models.py`):
---
{template}
---
""",
        },
        {
            "path": "app/schemas.py",
            "template": "app/schemas.py",
            "language": "python",
            "description": "app/schemas.py — swap Task* schemas for {item_class}*",
            "prompt": """\
Rewrite `app/schemas.py`. Keep `UserSchema`, `UserProfileSchema`,
`RegisterSchema`, `LoginSchema`, `OAuthLoginSchema`, `RefreshSchema`,
`ItemSchema`, `ItemCreateSchema`, and `ReactStateUpsertSchema` EXACTLY
as in the REFERENCE — the `Item*` and `ReactState*` schemas back the
wrapper-shared `/api/items` and `/api/state` endpoints the React
frontend consumes.

Update `ProjectSchema` so its reverse-accessor field for the new entity
matches the user's `{item_name}`:
- Rename the `task_count: int` field to `{item_name}_count: int`.
- Update `ProjectSchema.from_model` so it calls `obj.{items_plural}.count()`
  instead of `obj.tasks.count()` (the new model uses
  `related_name='{items_plural}'` on the FK).
- Keep every other field in `ProjectSchema` and `ProjectCreateSchema`
  identical to the REFERENCE.

Replace `TaskSchema`, `TaskDetailSchema`, and `TaskCreateSchema` with
`{item_class}Schema`, `{item_class}DetailSchema`, and
`{item_class}CreateSchema`. The shapes must mirror the REFERENCE exactly:

- `{item_class}Schema(msgspec.Struct)`: `id`, `title`, `description`,
  `project_id`, `assignee_id` (`int | None`), `priority`, `status`,
  `is_completed`, `created_at`, `updated_at`. Provide a `from_model`
  classmethod that maps each field.
- `{item_class}DetailSchema`: same fields as `{item_class}Schema` plus
  `project: ProjectSchema` and `assignee: UserSchema | None`. Provide a
  `from_model` classmethod that calls `ProjectSchema.from_model(obj.project)`
  and `UserSchema.from_model(obj.assignee) if obj.assignee else None`.
- `{item_class}CreateSchema(msgspec.Struct, kw_only=True)`: `title`,
  `project: int`, `description: str = ""`, `assignee: int | None = None`,
  `priority: str = "medium"`, `status: str = "todo"`. Use `kw_only=True`
  because the required `project` field follows optional `description`.

Update the `from app.models import ...` line so it imports
`{item_class}` instead of `Task`. Keep imports otherwise identical to the
REFERENCE.

REFERENCE (current `app/schemas.py`):
---
{template}
---
""",
        },
        {
            "path": "app/services/auth_service.py",
            "template": "app/services/auth_service.py",
            "language": "python",
            "description": "app/services/auth_service.py — shared-secret JWT helpers",
            "prompt": """\
Rewrite `app/services/auth_service.py`.

The auth_service is independent of the user's `{item_class}` choice — it
only deals with users, JWT tokens, and OAuth. Keep the REFERENCE almost
verbatim — including how it pulls `settings.JWT_SECRET`,
`settings.JWT_ALGORITHM`, `settings.JWT_ISSUER`, `settings.JWT_ACCESS_TTL`
and `settings.JWT_REFRESH_TTL` from the shared environment, and how
`Token.decode` is called with `settings.JWT_SECRET`.

CRITICAL: NEVER replace `settings.JWT_SECRET` with `settings.SECRET_KEY`.
The first is the wrapper-shared JWT secret (so a token issued here is
accepted by every other service in the project); the second is a
Django-specific salt that differs per service.

Apply exactly one optional change driven by `{auth_type}`:
- If `{auth_type}` is `oauth` and the user supplied notes
  (`{auth_details}`), add a one-line comment above the `oauth_login`
  method summarising those notes.
- For every other `{auth_type}`, leave the file identical to the
  REFERENCE.

Imports must remain `from django.conf import settings`,
`from django.contrib.auth.models import User`,
`from django_bolt import Token, create_jwt_for_user`.

REFERENCE (current `app/services/auth_service.py`):
---
{template}
---
""",
        },
        {
            "path": "app/api.py",
            "template": "app/api.py",
            "language": "python",
            "description": "app/api.py — BoltAPI endpoints + {item_class}ViewSet",
            "prompt": """\
Rewrite `app/api.py`.

Keep all of the REFERENCE intact except for the `Task`-related parts.
**The `ItemViewSet` and the three `react_state_*` handlers
(`react_state_load`, `react_state_upsert`, `react_state_delete`) at
the bottom of the file MUST be preserved verbatim** — they back the
wrapper-shared `/api/items` and `/api/state` endpoints the React
frontend consumes.

- Update the `from app.models import ...` line so it imports
  `{item_class}` alongside `Item`, `ReactState`, etc. (do NOT remove
  `Item` or `ReactState`).
- Update the `from app.schemas import (...)` block so it imports
  `{item_class}Schema`, `{item_class}DetailSchema`, and
  `{item_class}CreateSchema` alongside the existing `ItemSchema`,
  `ItemCreateSchema`, and `ReactStateUpsertSchema`.
- Replace the `TaskViewSet` class (mounted at `/api/{items_plural}`) with
  `{item_class}ViewSet(ModelViewSet)`. The viewset must:
  - Use `serializer_class = {item_class}Schema`.
  - Use `pagination_class = PageNumberPagination`.
  - Implement `get_queryset` filtering by `project__owner=user` with
    `select_related('project', 'assignee')`.
  - Implement async `list`, `create`, `retrieve` methods that mirror the
    REFERENCE patterns (use `{item_class}Schema.from_model` /
    `{item_class}DetailSchema.from_model`).
  - Implement `@action(methods=['PATCH'], detail=True) async def assign`
    that decodes the JSON body, looks up the assignee via
    `User.objects.aget`, returns 404 if missing, and updates the
    `{item_name}` instance.
  - Implement `@action(methods=['PATCH'], detail=True) async def complete`
    that sets `is_completed = True` and `status = 'done'`.

Authentication style for the viewset:
- When `{auth_type}` is `none`, mount the viewset with `guards=[AllowAny()]`
  and drop the `current_user` plumbing — the queryset becomes
  `{item_class}.objects.all().select_related('project', 'assignee')`.
- For any other `{auth_type}` value, keep
  `auth=[JWTAuthentication()], guards=[IsAuthenticated()]` exactly as the
  REFERENCE uses them.

Keep the auth endpoints (`register`, `login`, `oauth_login`, `refresh`,
`get_profile`, `update_profile`) and the `ProjectViewSet` exactly as in
the REFERENCE.

REFERENCE (current `app/api.py`):
---
{template}
---
""",
        },
        {
            "path": "app/tests/test_models.py",
            "template": "app/tests/test_models.py",
            "language": "python",
            "description": "app/tests/test_models.py — unit tests for {item_class}",
            "prompt": """\
Rewrite `app/tests/test_models.py`.

Keep the `UserProfile`, `Project`, and `AuthService` tests intact. Replace
the `Task`-specific tests with equivalent ones for `{item_class}`:

- `test_{item_name}_defaults_and_choices`: create a project, then a
  `{item_class}(project=project, title='Write tests')`. Assert
  `priority == 'medium'`, `status == 'todo'`, `is_completed is False`,
  `str(item) == 'Write tests'`.
- `test_{item_name}_assignee_optional`: create a `{item_class}` with an
  assignee, assert `item.assignee == user`.

Update imports: `from app.models import Project, {item_class}, UserProfile`.

REFERENCE (current `app/tests/test_models.py`):
---
{template}
---
""",
        },
        {
            "path": "app/tests/test_api.py",
            "template": "app/tests/test_api.py",
            "language": "python",
            "description": "app/tests/test_api.py — schema + flow tests",
            "prompt": """\
Rewrite `app/tests/test_api.py`.

Keep `test_user_schema_from_model`, `test_user_profile_schema_from_model`,
`test_register_schema_construction`, and `test_register_then_login_flow`
intact.

Rename `test_project_schema_task_count` to
`test_project_schema_{item_name}_count`, create three `{item_class}` rows
on the project, and assert
`schema.{item_name}_count == 3`. The accessor is now named
`{item_name}_count` because `ProjectSchema` was updated to use the new
entity's reverse-relationship name.

Replace the `Task`-specific tests with equivalent ones for `{item_class}`:

- `test_{item_name}_schema_from_model`: create a Project + `{item_class}`,
  call `{item_class}Schema.from_model(item)`, assert title / project_id /
  priority / status.
- `test_{item_name}_detail_schema_with_assignee`: create a `{item_class}`
  with an assignee, call `{item_class}DetailSchema.from_model(item)`,
  assert nested `project.id` and `assignee.id`.
- `test_owner_isolation_for_{items_plural}`: create projects and
  `{items_plural}` for two users, filter by `project__owner=alice`,
  assert isolation.
- `test_{item_name}_completion_flow`: create a `{item_class}`, set
  `is_completed=True` and `status='done'`, save, and re-read it.
- `test_{item_name}_cascade_on_project_delete`: create a `{item_class}`
  on a project, save the project id, delete the project, assert
  `{item_class}.objects.filter(project_id=pid).count() == 0`.

Imports: `from app.models import Project, {item_class}, UserProfile`,
`from app.schemas import (..., {item_class}Schema, {item_class}DetailSchema, ...)`.

REFERENCE (current `app/tests/test_api.py`):
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
# After the per-target MANIFEST above generates the new django-bolt
# service, ``_bin/skel-gen-ai`` runs a SECOND Ollama pass against the
# block below. The integration phase has access to a snapshot of every
# sibling service in the wrapper via the ``{wrapper_snapshot}``
# placeholder so the model can ground its rewrites in real code.
#
# Targets here are *additive* — they create new files (sibling clients,
# integration tests) without overwriting anything from the first phase.
# Each target's prompt receives the same template variables as the
# main MANIFEST plus:
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
You are a senior django-bolt engineer integrating a freshly generated
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`python-django-bolt-skel`). It already ships:
- The wrapper-shared `Item` model + `ItemViewSet` mounted at `/api/items`.
- The wrapper-shared `ReactState` model + `react_state_*` handlers
  mounted at `/api/state` and `/api/state/{{key}}`.
- A user-chosen `{item_class}` model + viewset (the per-target manifest
  rewrote `Task` to `{item_class}` for this run).
- JWT auth via `JWTAuthentication()` + `IsAuthenticated()` from
  django-bolt, signed with `settings.JWT_SECRET` (the wrapper-shared
  secret — NEVER `settings.SECRET_KEY`).
- The wrapper-shared `<wrapper>/.env` is loaded by `app/settings.py`
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
- Use **django-bolt** primitives only (`BoltAPI`, `JSON`, `Token`,
  `JWTAuthentication`, etc.). Do NOT introduce DRF, simplejwt,
  django-filter, or any other DRF-ecosystem package.
- Use `from django.contrib.auth.models import User` directly.
- Use `pytest` + `pytest-django` (already pinned in
  `requirements.txt`). Mark async tests with `@pytest.mark.asyncio`.
- Read JWT material via `from django.conf import settings` and
  reference `settings.JWT_SECRET` (NOT `settings.SECRET_KEY`).
- Read `DATABASE_URL` indirectly via the existing `_build_databases()`
  helper — do NOT touch `settings.py` from these prompts.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items`, `/api/state`, and
  `/api/{items_plural}` endpoints. Do not assume sibling services
  exist; gracefully degrade.

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
    "fix_timeout_m": 60,
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
  `httpx` / `requests` dependency — keep the django-bolt service
  dependency-light).
- Each sibling backend gets a class named `<PascalSlug>Client`
  (e.g. `WebUiClient`, `AuthApiClient`). The class:
    - Reads its base URL from `os.environ["SERVICE_URL_<UPPER_SLUG>"]`
      in `__init__`. Raise `RuntimeError` with a clear message when
      the env var is missing.
    - Accepts an optional `token: str | None` parameter; when set,
      every request sends `Authorization: Bearer <token>`.
    - Exposes `list_items()` and `get_state(key: str)` async-or-sync
      methods that hit the sibling's wrapper-shared `/api/items` and
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
- All tests MUST be **synchronous** (plain `def`, NOT `async def`).
  Django's `@pytest.mark.django_db` does NOT support async tests.
  Do NOT use `@pytest.mark.asyncio`. Do NOT use async ORM methods
  like `acreate`, `aupdate_or_create`, `aget`, etc.
  Use the synchronous ORM: `objects.create()`, `objects.get()`,
  `objects.update_or_create()`, `objects.filter()`, `objects.all()`.
- `ReactState.value` is a `JSONField` — it stores native Python
  objects (dicts, lists, strings, numbers). You can assign a dict
  directly and read it back as a dict. Do NOT use `json.dumps()`
  or `json.loads()`.
- When testing sibling clients, the `SERVICE_URL_<SLUG>` env var
  may not be set (e.g. in CI or when the sibling isn't running).
  Always guard client instantiation with `try/except` and call
  `pytest.skip()` when the env var is missing or the service is
  unreachable.

Required tests (every test must use `@pytest.mark.django_db`):

1. `test_items_endpoint_round_trip` — create an `Item` via
   `Item.objects.create(name=..., description=...)`, then assert
   the same row appears in `Item.objects.all()`.

2. `test_react_state_round_trip` — create a test user, then use
   `ReactState.objects.update_or_create(user=user, key="test_key",
   defaults={{"value": {{"some": "data"}}}})`, read it back with
   `ReactState.objects.get(user=user, key="test_key")`, and assert
   `state.value == {{"some": "data"}}`.

3. `test_{items_plural}_endpoint_uses_jwt` — register a user via
   `AuthService.register_user("testuser", "test@example.com", "testpass123")`,
   (signature is `register_user(username, email, password)` — all 3 required),
   then mint a JWT via `AuthService.authenticate_user("testuser", "testpass123")`,
   and assert the result is not None, contains an `"access"` key with a
   non-empty string value.

4. `test_jwt_secret_is_wrapper_shared` — assert that
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
- `from django.conf import settings`
- `from django.contrib.auth.models import User`
- `from app.models import Item, ReactState`
- `from app.services.auth_service import AuthService`
- (when {sibling_count} > 0) `from app.integrations.sibling_clients import IntegrationError, ...`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
