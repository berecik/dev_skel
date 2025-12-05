# python-fastapi-skel

**Location**: `_skels/python-fastapi-skel/`

**Framework**: FastAPI with async SQLAlchemy

## Structure

```
python-fastapi-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Pydantic settings
│   ├── database.py      # Async SQLAlchemy setup
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   └── routes.py        # API routes
└── tests/
    ├── __init__.py
    └── test_main.py
```

## Dependencies Installed

- fastapi
- uvicorn
- sqlalchemy
- aiosqlite
- pydantic-settings
- alembic
- python-dotenv

## Generation

From repo root:
```bash
make gen-python-fastapi NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen python-fastapi <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Layout

When you generate a FastAPI project, the target path is the **wrapper directory** (`main_dir`) and the real project lives in an inner `backend/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./backend/run, ./backend/test, ...
  backend/       # real FastAPI project (venv, code, Dockerfile, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `backend/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./backend/test)
./test

# Start development server (delegates to ./backend/run)
./run dev

# Start production server
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
| `./test` | Run pytest tests (`-q` for quiet, `--cov` for coverage) |
| `./build` | Build Docker image (`--tag=NAME`, `--no-cache`, `--push`) |
| `./run` | Run server (`dev`, `prod`, `docker`) |
| `./stop` | Stop Docker container |

## Testing

Test the skeleton (E2E):
```bash
cd _skels/python-fastapi-skel
make test   # runs bash ./test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.
