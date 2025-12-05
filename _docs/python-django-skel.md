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

## Generated Project Layout

When you generate a Django project, the target path is the **wrapper directory** (`main_dir`) and the real project lives in an inner `backend/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./backend/run, ./backend/test, ...
  backend/       # real Django project (venv, manage.py, settings, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `backend/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./backend/test)
./test

# Start development server (delegates to ./backend/run)
./run dev

# Start production server (gunicorn)
./run prod

# Build and run in Docker
./build
./run docker

# Stop services
./stop
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run pytest tests |
| `./build` | Build Docker image (`--tag=NAME`, `--no-cache`, `--push`) |
| `./run` | Run server (`dev`, `prod`, `docker`) |
| `./stop` | Stop Docker container |

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
