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

## Generated Project Usage

```bash
cd myapp
source .venv/bin/activate
python run.py
# or: flask run
```

## Testing

Test the skeleton (E2E):
```bash
cd _skels/python-flask-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.
