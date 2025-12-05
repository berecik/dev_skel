# python-flask-skel

**Location**: `_skels/python-flask-skel/`

**Framework**: Flask with Flask-SQLAlchemy

## Structure

```
python-flask-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── run.py               # Entry point
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── config.py        # Configuration
│   ├── models.py        # SQLAlchemy models
│   └── routes.py        # Blueprint routes
└── tests/
    ├── __init__.py
    └── test_routes.py
```

## Dependencies Installed

- flask
- flask-sqlalchemy
- flask-migrate
- python-dotenv
- gunicorn

## Generation

From repo root:
```bash
make gen-python-flask NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen python-flask <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Layout

When you generate a Flask project, the target path is the **wrapper directory** (`main_dir`) and the real project lives in an inner `backend/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./backend/run, ./backend/test, ...
  backend/       # real Flask project (venv, code, Dockerfile, etc.)
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
cd _skels/python-flask-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.
