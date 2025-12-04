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

## Generated Project Usage

```bash
cd myapp
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Testing

Test the skeleton (E2E):
```bash
cd _skels/python-fastapi-skel
make test   # runs bash ./test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.
