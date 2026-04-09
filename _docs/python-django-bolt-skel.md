# python-django-bolt-skel

**Location**: `_skels/python-django-bolt-skel/`

**Framework**: Django + [django-bolt](https://github.com/dj-bolt/django-bolt) (Actix Web + PyO3 — ~60k RPS) + msgspec

This skeleton mirrors the layout of the project that
[`claude_on_django`](https://github.com/beret/claude_on_django) generates,
so you can move freely between hand-coded and AI-generated services.

## Stack

| Layer | Choice |
|-------|--------|
| API framework | django-bolt (`BoltAPI`, `ModelViewSet`, `@action`) |
| Serialization | `msgspec.Struct` |
| Authentication | JWT via `create_jwt_for_user` / `Token` from django-bolt |
| Permissions | `JWTAuthentication`, `IsAuthenticated`, `AllowAny` guards |
| Pagination | `PageNumberPagination` |
| Database | Async Django ORM (`aget`, `acreate`, `asave`, `adelete`) |
| Runtime | `python manage.py runbolt --dev` |

## Structure

```
python-django-bolt-skel/
├── Makefile
├── pyproject.toml          # pytest config (DJANGO_SETTINGS_MODULE, --nomigrations)
├── conftest.py
├── manage.py
├── requirements.txt        # production deps
├── requirements-dev.txt    # adds pytest + pytest-django
├── gen / merge / test_skel
├── deps / install-deps
├── build / build-dev
├── run / run-dev / stop / stop-dev
├── test
└── app/
    ├── __init__.py
    ├── settings.py         # registers django_bolt + app
    ├── urls.py             # ROOT_URLCONF = [] (django-bolt routes via decorators)
    ├── models.py           # UserProfile, Project, Task + post_save signal
    ├── schemas.py          # msgspec.Struct schemas with from_model() helpers
    ├── api.py              # BoltAPI endpoints + ModelViewSets
    ├── services/
    │   ├── __init__.py
    │   └── auth_service.py # JWT register/login/oauth/refresh
    ├── migrations/
    │   └── __init__.py
    └── tests/
        ├── __init__.py
        ├── test_models.py  # Models + AuthService unit tests
        └── test_api.py     # Schema + service-flow integration tests
```

## Dependencies Installed

- `django>=4.2`
- `django-bolt>=0.7`
- `msgspec>=0.18`
- `python-dotenv`
- `gunicorn`
- (dev) `pytest`, `pytest-django`, `pytest-asyncio`

## Generation Notes

- The skeleton **does not** call `django-admin startproject`. Everything
  needed lives inside the skeleton tree and is copied verbatim by `merge`.
- The Django app is named `app` (single-app convention).
  `ROOT_URLCONF = 'app.urls'` and `app.urls.urlpatterns = []` — every
  endpoint lives on the `BoltAPI()` instance in `app/api.py`.
- The skeleton ships **without** migration files. The pytest config sets
  `addopts = "--nomigrations"` so the test suite still passes; once you
  generate real migrations (`python manage.py makemigrations app`) you can
  drop that flag.

## Generation

From repo root:
```bash
make gen-django-bolt NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen python-django-bolt-skel <target-path>
```

Interactive AI generation (Ollama):
```bash
_bin/skel-gen-ai python-django-bolt-skel <target-path>
```

## Generated Project Layout

```text
myapp/
  README.md      # generic wrapper README
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts
  backend/       # the django-bolt service
    manage.py
    app/         # settings, urls, models, schemas, api, services, tests
    .venv/
```

## Generated Project Usage

```bash
cd myapp
./install-deps           # build the local virtualenv
./run dev                # python manage.py runbolt --dev
./test                   # pytest
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run pytest tests (forwards to `./backend/test`) |
| `./build` | Refresh local virtualenv (`./build --release` for prod-only deps) |
| `./run` | Run django-bolt (`dev` mode by default) |
| `./stop` | Stop any running `manage.py runbolt` processes |

## Endpoints (out of the box)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | User registration |
| POST | `/api/auth/login` | JWT login |
| POST | `/api/auth/oauth` | OAuth login (Google, Apple) |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET / PATCH | `/api/auth/profile` | User profile |
| GET / POST / DELETE | `/api/projects[/{id}]` | Project CRUD |
| GET / POST | `/api/tasks` | List/create tasks |
| GET | `/api/tasks/{id}` | Task detail |
| PATCH | `/api/tasks/{id}/assign` | Assign task |
| PATCH | `/api/tasks/{id}/complete` | Mark task complete |

## AI Generation

`_skels/_common/manifests/python-django-bolt-skel.py` tells `skel-gen-ai`
which files to rewrite when the user runs `_bin/skel-gen-ai
python-django-bolt-skel ...`. The interactive dialog collects:

- **Service display name** (used in comments and slugs)
- **Item name** — replaces the reference `Task` entity throughout
  `models.py`, `schemas.py`, `api.py`, and the test files
- **Auth type** — `none` flips the viewset to `AllowAny()` and drops the
  `current_user` plumbing; any other value keeps the JWT-protected
  flow exactly as the reference uses it
- **Auth notes** — freeform text passed into the prompts (e.g. "OAuth via
  Google only")

`UserProfile`, `Project`, and the auth endpoints stay unchanged across
generations so registration / login / refresh keep working out of the box.

## Testing

Test the skeleton end-to-end:

```bash
make test-gen-django-bolt   # generate + import + manage.py check
make test-django-bolt       # generate + run pytest suite
```

Inside a generated project:

```bash
./test                       # pytest
./test --check               # python manage.py check
./test --cov                 # pytest with coverage
```

## Merge Script Exclusions

The merge script excludes generator-owned files at the skeleton root so
they do not leak into the generated project:

- `Makefile`, `gen`, `merge`, `test_skel`, `deps`, `install-deps`
- `AGENTS.md`, `CLAUDE.md`, `JUNIE-RULES.md`
- Everything under `.git/`, `.pytest_cache/`, `__pycache__/`, `.venv/`,
  `_scripts/`
