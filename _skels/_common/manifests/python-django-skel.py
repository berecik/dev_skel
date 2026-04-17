"""AI manifest for the ``python-django-skel`` skeleton.

Loaded by ``_bin/skel-gen-ai`` to know which files to regenerate with Ollama
after the base skeleton has been scaffolded. Each entry references a *template*
file that already lives inside the skeleton tree — those files are read into
the prompt as the REFERENCE block so the AI has a concrete starting point.

Placeholders use Python ``str.format`` syntax. The available variables come
from :class:`skel_ai_lib.GenerationContext`:

    {skeleton_name}, {project_name}, {service_subdir}, {service_label},
    {service_slug}, {item_name}, {item_class}, {items_plural}, {auth_type},
    {auth_details}, and {template} (the REFERENCE file's contents).

To extend this manifest:
- Add new dicts under ``targets``.
- Each ``path`` is relative to the generated service directory
  (e.g. ``backend/`` inside the wrapper).
- ``template`` is relative to the skeleton root
  (``_skels/python-django-skel/...``). Use ``None`` if there is no template.

The generator does not run Django commands itself — re-run
``./install-deps`` and ``manage.py makemigrations`` after AI overlay.
"""

SYSTEM_PROMPT = """\
You are a senior Django backend engineer regenerating part of a Django service
generated from the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Django project package is `myproject` (settings, urls, wsgi, asgi).
- The on-disk service directory inside the wrapper `{project_name}/` is
  `{service_subdir}/` (= the slug of the user's `{service_label}`).
- The new Django app introduced for the user's CRUD entity is named
  `{service_slug}` and lives at `{service_slug}/` inside the service dir.
- ROOT_URLCONF is `myproject.urls`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).

Shared environment (CRITICAL — every backend service in the wrapper uses
the same env vars sourced from `<wrapper>/.env`):
- `DATABASE_URL` — common database connection. settings.py already wires
  the resolution logic; never hardcode a sqlite path.
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL` — shared JWT material so a token issued by one
  service in the wrapper is accepted by every other service. Read them
  via `os.environ.get(...)` or `from django.conf import settings` and use
  `settings.JWT_SECRET` (NEVER `settings.SECRET_KEY` for token signing).

Authentication style requested by the user: `{auth_type}`.
Extra auth notes: {auth_details}

Coding rules:
- Use Django's stdlib ORM and `django.contrib.auth.models.User` directly.
- Prefer Django REST-free patterns (plain `JsonResponse` or class-based views)
  unless the REFERENCE template clearly imports DRF.
- Match the indentation, quoting style, and import order of the REFERENCE
  template. Do NOT introduce new third-party dependencies beyond what the
  reference file already uses.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `python manage.py makemigrations {service_slug} && python manage.py "
        "migrate` after generation to materialise the new app."
    ),
    "targets": [
        {
            "path": "myproject/settings.py",
            "template": "myproject/settings.py",
            "language": "python",
            "description": "settings.py — register the new app + auth backend",
            "prompt": """\
Update Django `settings.py` for the `{service_label}` service.

Start from the REFERENCE settings below and adapt it as follows:
- Add `'{service_slug}'` to INSTALLED_APPS (after the contrib apps).
- Keep all existing middleware and template configuration intact.
- KEEP the existing wrapper-shared `.env` loading block, the JWT_* env
  reads, and the `_build_databases()` helper EXACTLY AS THEY APPEAR IN
  THE REFERENCE. Reproduce them character-for-character. The exact
  block at the top of the file MUST stay as:

    BASE_DIR = Path(__file__).resolve().parent.parent

    WRAPPER_ENV = BASE_DIR.parent / ".env"
    if WRAPPER_ENV.is_file():
        load_dotenv(WRAPPER_ENV)
    load_dotenv(BASE_DIR / ".env")

  Note the closing parens on both `load_dotenv(...)` calls — both must
  be present and balanced. Likewise the `_build_databases()` helper and
  its `DATABASES = _build_databases()` assignment must appear verbatim,
  with every parenthesis closed.
- If `{auth_type}` is `jwt` or `oauth`, add a one-line comment above
  MIDDLEWARE noting that token auth is handled in views (do not import
  any third-party packages).
- If `{auth_type}` is `session`, leave the existing session middleware
  as-is.
- Do NOT introduce djangorestframework, simplejwt, dj-database-url, or
  any package that is not already in the reference. Stay stdlib + Django
  + python-dotenv.
- Before you stop generating, mentally re-read the file you produced
  and confirm every `(` has a matching `)` and every `{{` a matching
  `}}`. Truncated parens here cause the entire test suite to fail.

REFERENCE (current settings.py):
---
{template}
---

Output ONLY the new file contents.
""",
        },
        {
            "path": "myproject/urls.py",
            "template": "myproject/urls.py",
            "language": "python",
            "description": "urls.py — wire `{service_slug}` routes under /api/{items_plural}",
            "prompt": """\
Rewrite `myproject/urls.py` so the new `{service_slug}` app is mounted under
`/api/{items_plural}/`.

- Keep the existing `index` and `health` views from the REFERENCE.
- Add `path('api/{items_plural}/', include('{service_slug}.urls'))`.
- Keep `path('admin/', admin.site.urls)`.
- Import `include` from `django.urls`.
- Output only the file contents.

REFERENCE (current urls.py):
---
{template}
---
""",
        },
        {
            "path": "{service_slug}/__init__.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/__init__.py — empty app marker",
            "prompt": "Output a single empty Python file (no content, no comments).",
        },
        {
            "path": "{service_slug}/apps.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/apps.py — Django AppConfig",
            "prompt": """\
Generate a Django `AppConfig` for the `{service_slug}` app.

- Class name: `{item_class}Config`.
- `default_auto_field = 'django.db.models.BigAutoField'`.
- `name = '{service_slug}'`.
- No imports beyond `from django.apps import AppConfig`.
- Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/models.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/models.py — `{item_class}` model",
            "prompt": """\
Generate `{service_slug}/models.py` for a service named `{service_label}`.

Define a single Django model `{item_class}` with these fields:
- `title`: CharField(max_length=200)
- `description`: TextField(blank=True, default='')
- `status`: CharField with TextChoices `Status` (todo / in_progress / done,
  default `todo`)
- `priority`: CharField with TextChoices `Priority` (low / medium / high,
  default `medium`)
- `is_completed`: BooleanField(default=False)
- `created_at`: DateTimeField(auto_now_add=True)
- `updated_at`: DateTimeField(auto_now=True)
- `owner`: ForeignKey('auth.User',
    related_name='{items_plural}',
    on_delete=models.CASCADE,
    null={auth_is_none},
    blank={auth_is_none})

The user chose auth style `{auth_type}`. The `null=`/`blank=` flags above
are `True` only when no authentication is in use (so anonymous items are
allowed); otherwise the owner is required.

Use `class Meta: ordering = ['-created_at']` and `__str__` returning
`self.title`.

Imports: only `from django.db import models`. Do not import anything else.
Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/admin.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/admin.py — register `{item_class}` in admin",
            "prompt": """\
Generate `{service_slug}/admin.py` registering the `{item_class}` model.

- Use `@admin.register({item_class})`.
- `list_display = ('id', 'title', 'status', 'priority', 'is_completed', 'created_at')`.
- `list_filter = ('status', 'priority', 'is_completed')`.
- `search_fields = ('title', 'description')`.
- Imports: `from django.contrib import admin` and
  `from .models import {item_class}`.
- Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/views.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/views.py — CRUD endpoints for `{item_class}`",
            "prompt": """\
Generate `{service_slug}/views.py` exposing CRUD endpoints for `{item_class}`.

Use plain Django views (no DRF). Each view returns `JsonResponse`.

The companion `urls.py` will route to these EXACT function names — do
NOT rename them or split them into more views:

- `def list_or_create(request)` — handles both `GET /` (list, paginated
  by `?limit=` query, default 50) and `POST /` (create from JSON body).
  Use `if request.method == 'GET': ... elif request.method == 'POST': ...`
  inside the same function. Return 405 for any other method.
- `def retrieve_update_destroy(request, pk)` — handles `GET /<pk>/`
  (retrieve), `PATCH /<pk>/` (partial update from JSON body), and
  `DELETE /<pk>/` (destroy). Branch on `request.method` inside the same
  function and return 405 for anything else.
- `def complete(request, pk)` — handles `POST /<pk>/complete/`. Set
  `is_completed=True` and `status='done'` and return the updated item.
  Return 405 for non-POST.

Authentication style for this service: `{auth_type}`.
- `none`: no authentication, no `request.user` checks.
- `session`: use `@login_required`; filter list/retrieve to `owner=request.user`.
- `basic`: same as session but document HTTP Basic in a top-level docstring.
- `jwt` / `oauth` / `api_key`: read a `Bearer` token from the
  `Authorization` header and verify it via the wrapper-shared
  `JWT_SECRET`. Add a helper `_user_from_token(request)` that:
  1. Reads `Authorization: Bearer <token>` from the request.
  2. Decodes it with `jwt.decode(token, settings.JWT_SECRET,
     algorithms=[settings.JWT_ALGORITHM], issuer=settings.JWT_ISSUER)`
     where `jwt` is `import jwt` (PyJWT).
  3. Returns the matching `User` (looked up by the `sub` claim) or
     `None` on failure.
  Reject with 401 when the helper returns `None`. Filter list/retrieve to
  `owner=user` once the helper resolved a user. Add `import jwt` and
  `from django.conf import settings` to the imports.

Notes:
- Use `csrf_exempt` on POST/PATCH/DELETE handlers since the API is JSON-only.
- Decode request bodies with `json.loads(request.body or b'{{}}')`.
- Filter querysets by `owner=request.user` whenever auth is enabled.
- Always return JSON; never raise unhandled exceptions on bad input — return
  status 400 with `{{'error': '...'}}`.
- Imports: `json`, `from django.http import JsonResponse, HttpResponseNotAllowed`,
  `from django.views.decorators.csrf import csrf_exempt`,
  `from django.contrib.auth.decorators import login_required`,
  `from django.shortcuts import get_object_or_404`,
  `from .models import {item_class}`.

Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/urls.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/urls.py — route table for `{item_class}`",
            "prompt": """\
Generate `{service_slug}/urls.py` mapping the views from
`{service_slug}.views` to URL patterns.

Patterns (relative to the include path `/api/{items_plural}/`):
- `''` → `views.list_or_create`, name `'{item_name}-list'`
- `'<int:pk>/'` → `views.retrieve_update_destroy`, name `'{item_name}-detail'`
- `'<int:pk>/complete/'` → `views.complete`, name `'{item_name}-complete'`

Imports: `from django.urls import path` and `from . import views`.
Define `app_name = '{service_slug}'`.
Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/tests.py",
            "template": "tests/test_views.py",
            "language": "python",
            "description": "{service_slug}/tests.py — pytest-django tests for `{item_class}`",
            "prompt": """\
Generate `{service_slug}/tests.py` using pytest-django (the project already
has a `conftest.py`). Reuse the patterns from the REFERENCE test file.

Cover at least:
- `test_list_empty` — GET returns 200 and an empty list.
- `test_create_{item_name}` — POST creates a `{item_class}` and returns 201.
- `test_retrieve_{item_name}` — GET by id returns the item.
- `test_complete_endpoint` — POST `/<id>/complete/` flips
  `is_completed=True` and `status='done'`.
- `test_filter_by_owner` — only relevant when `{auth_type}` is not `none`.

Authentication setup hints:
- `none`: do not create users; use `Client()` directly.
- `session` / `basic`: create a `User` and call `client.force_login(user)`.
- `jwt` / `oauth` / `api_key`: create a user and skip token plumbing — call
  `client.force_login(user)` and add a `# TODO: replace with real token` note
  near the auth setup.

Imports: `pytest`, `from django.contrib.auth.models import User`,
`from django.test import Client`, `from {service_slug}.models import {item_class}`.

REFERENCE (existing test file used as a style guide):
---
{template}
---

Output only the file contents.
""",
        },
        {
            "path": "{service_slug}/migrations/__init__.py",
            "template": None,
            "language": "python",
            "description": "{service_slug}/migrations/__init__.py — empty marker",
            "prompt": "Output a single empty Python file (no content, no comments).",
        },
    ],
}


# --------------------------------------------------------------------------- #
#  Integration manifest (second Ollama session)
# --------------------------------------------------------------------------- #
#
# After the per-target MANIFEST above generates the new django service,
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
You are a senior Django engineer integrating a freshly generated service
into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`python-django-skel`). It already ships:
- The wrapper-shared `Item`, `Category`, and `ReactState` models
  (defined in `app/models.py`) plus DRF `ItemViewSet` and
  `CategoryViewSet` mounted at `/api/items` and `/api/categories`.
- The wrapper-shared `ReactState` handlers (`StateView`,
  `StateKeyView`) mounted at `/api/state` and `/api/state/<key>`.
- A user-chosen `{item_class}` model + views generated by the
  per-target manifest into the `{service_slug}/` Django app
  (mounted at `/api/{items_plural}/`).
- JWT auth via DRF + simplejwt, signed with `settings.JWT_SECRET`
  (the wrapper-shared secret — NEVER `settings.SECRET_KEY`).
  `settings.JWT_SECRET` is read from the wrapper `.env` and wired
  into simplejwt's `SIGNING_KEY`.
- The wrapper-shared `<wrapper>/.env` is loaded by
  `myproject/settings.py` before the local `.env` so `DATABASE_URL`
  and the JWT vars are identical to every other backend in the project.

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
- Use **Django REST Framework** (DRF) + **simplejwt** — the same
  libraries the wrapper-shared views already use. Do NOT introduce
  django-bolt, django-ninja, or any other API framework.
- Use `from django.contrib.auth.models import User` directly.
- Use `pytest` + `pytest-django` (already pinned in
  `requirements.txt`). All tests MUST be synchronous (plain `def`,
  NOT `async def`). Use `@pytest.mark.django_db` on every test.
  Do NOT use `@pytest.mark.asyncio`.
- Read JWT material via `from django.conf import settings` and
  reference `settings.JWT_SECRET` (NOT `settings.SECRET_KEY`).
- Read `DATABASE_URL` indirectly via the existing `_build_databases()`
  helper — do NOT touch `settings.py` from these prompts.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items`, `/api/state`, and
  `/api/{items_plural}` endpoints via the Django ORM. Do not assume
  sibling services exist; gracefully degrade.

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
  `httpx` / `requests` dependency — keep the django service
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
  `@pytest.mark.django_db` does NOT support async tests.
  Do NOT use `@pytest.mark.asyncio`. Do NOT use async ORM methods.
  Use the synchronous ORM: `objects.create()`, `objects.get()`,
  `objects.update_or_create()`, `objects.filter()`, `objects.all()`.
- `ReactState.value` is a `TextField` — it stores opaque strings,
  NOT native Python dicts. Assign a string value and read it back as
  a string. Do NOT use `json.dumps()` or `json.loads()` unless you
  are deliberately serialising structured data into the text column.
- When testing sibling clients, the `SERVICE_URL_<SLUG>` env var
  may not be set (e.g. in CI or when the sibling isn't running).
  Always guard client instantiation with `try/except` and call
  `pytest.skip()` when the env var is missing or the service is
  unreachable.

Required tests (every test must use `@pytest.mark.django_db`):

1. `test_items_endpoint_round_trip` — create an `Item` via
   `Item.objects.create(name=..., description=...)`, then assert
   the same row appears in `Item.objects.all()`.

2. `test_react_state_round_trip` — create a test user via
   `User.objects.create_user(username=..., password=...)`, then use
   `ReactState.objects.update_or_create(user=user, key="test_key",
   defaults={{"value": "some_data"}})`, read it back with
   `ReactState.objects.get(user=user, key="test_key")`, and assert
   `state.value == "some_data"`.

3. `test_{items_plural}_endpoint_uses_jwt` — create a user via
   `User.objects.create_user("testuser", "test@example.com", "testpass123")`,
   then mint a JWT via `RefreshToken.for_user(user)`, and assert the
   result contains a non-empty `access_token` string.

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
- `from rest_framework_simplejwt.tokens import RefreshToken`
- `from app.models import Item, ReactState`
- (when {sibling_count} > 0) `from app.integrations.sibling_clients import IntegrationError, ...`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
