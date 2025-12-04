# python-django-skel

**Location**: `_skels/python-django-skel/`

**Framework**: Django

## Structure

```
python-django-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── conftest.py          # pytest configuration
├── manage.py
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── tests/
    ├── __init__.py
    └── test_views.py
```

## Dependencies Installed

- django
- python-dotenv
- gunicorn

## Generation Notes

- Uses `django-admin startproject` then overlays skeleton files
- Replaces default `urls.py` with skeleton version

## Generation

From repo root:
```bash
make gen-python-django NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen python-django <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Usage

```bash
cd myapp
source .venv/bin/activate
python manage.py runserver
```

## Testing

Test the skeleton (E2E):
```bash
cd _skels/python-django-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

### Merge Script Exclusions

- `manage.py`
- `myproject/__init__.py`
- `myproject/asgi.py`
- `myproject/settings.py`
- `myproject/urls.py`
- `myproject/wsgi.py`
