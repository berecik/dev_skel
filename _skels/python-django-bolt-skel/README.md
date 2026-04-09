# python-django-bolt-skel

A Django backend skeleton built on **[django-bolt](https://github.com/dj-bolt/django-bolt)**
— Django + Rust HTTP layer (Actix Web + PyO3) for ~60k RPS — and
**msgspec.Struct** for fast (de)serialisation.

The layout is intentionally close to the project that
[`claude_on_django`](https://github.com/beret/claude_on_django) generates, so
that you can move freely between hand-coded and AI-generated services.

## Stack

| Layer | Choice |
|-------|--------|
| API framework | django-bolt (`BoltAPI`, `ModelViewSet`, `@action`) |
| Serialization | `msgspec.Struct` (5–10× faster than DRF serializers) |
| Authentication | JWT via `create_jwt_for_user` / `Token` from django-bolt |
| Permissions | `JWTAuthentication`, `IsAuthenticated`, `AllowAny` guards |
| Pagination | `PageNumberPagination` |
| Database | Async Django ORM (`aget`, `acreate`, `asave`, `adelete`) |
| Runtime | Actix Web + PyO3 via `python manage.py runbolt` |

## Generated layout

```
backend/                       # service directory inside the wrapper
├── manage.py
├── conftest.py                # pytest-django configuration
├── pyproject.toml             # pytest config
├── requirements.txt           # production deps
├── requirements-dev.txt       # adds pytest + pytest-django
├── build / build-dev          # local virtualenv build
├── run   / run-dev            # `manage.py runbolt --dev`
├── stop  / stop-dev           # pkill -f manage.py runbolt
├── test                       # pytest forwarder
├── install-deps               # virtualenv + pip install
└── app/
    ├── settings.py            # Django settings (registers django_bolt + app)
    ├── urls.py                # ROOT_URLCONF = [] (django-bolt routes via decorators)
    ├── models.py              # UserProfile, Project, Task + post_save signal
    ├── schemas.py             # msgspec.Struct schemas with from_model() helpers
    ├── api.py                 # BoltAPI endpoints + ModelViewSets
    ├── services/
    │   └── auth_service.py    # JWT register/login/oauth/refresh
    ├── migrations/
    │   └── __init__.py
    └── tests/
        ├── test_models.py     # Models + AuthService unit tests
        └── test_api.py        # Schema + service-flow integration tests
```

## Endpoints (ships with the skeleton)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Username/email/password registration |
| POST | `/api/auth/login` | JWT login (`access` + `refresh`) |
| POST | `/api/auth/oauth` | Mock OAuth (Google, Apple) |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET / PATCH | `/api/auth/profile` | User profile |
| GET / POST | `/api/projects` | List / create projects (owner-isolated) |
| GET / DELETE | `/api/projects/{id}` | Project detail / destroy |
| GET / POST | `/api/tasks` | List / create tasks |
| GET | `/api/tasks/{id}` | Task detail (with nested project + assignee) |
| PATCH | `/api/tasks/{id}/assign` | Assign a task |
| PATCH | `/api/tasks/{id}/complete` | Mark a task complete |

## Quick start

```bash
# 1) Generate from the dev_skel root
make gen-django-bolt NAME=myproj
cd myproj

# 2) Inspect the generated layout
ls
# README.md  Makefile  run  test  build  stop  install-deps  backend/

# 3) Build the local virtualenv
./install-deps     # or: ./build-dev

# 4) Apply migrations and start the django-bolt server
cd backend
. .venv/bin/activate
python manage.py migrate
python manage.py runbolt --dev
```

## AI generation

This skeleton has an AI manifest at
`_skels/_common/manifests/python-django-bolt-skel.py` consumed by
`_bin/skel-gen-ai`. Run an interactive dialog (service display name, item
entity, authentication style) to ask Ollama to rewrite `models.py`,
`schemas.py`, `api.py`, `services/auth_service.py`, and the test files for
your specific entity:

```bash
_bin/skel-gen-ai python-django-bolt-skel myproj
```

See the global README and `_docs/LLM-MAINTENANCE.md` for the dialog flow,
manifest format, and Ollama configuration.

## Testing

```bash
./test                  # forwards to pytest
./test --check          # python manage.py check
./test --cov            # pytest with coverage
```

The skeleton end-to-end test (`test_skel`) generates a temp project and
verifies that the test suite passes. It runs as part of
`make test-generators` and `make test-django-bolt` from the repo root.
