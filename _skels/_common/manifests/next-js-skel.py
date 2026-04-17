"""AI manifest for the ``next-js-skel`` skeleton.

The Node skeleton ships a tiny `src/index.js` that imports the
wrapper-shared `config` from `src/config.js` and prints the bound
host/port + database URL + JWT issuer. This manifest tells
``_bin/skel-gen-ai`` how to add a `{item_class}` CRUD module — a
`src/{item_name}.js` handler file with stdlib `node:sqlite` queries
against the wrapper-shared `DATABASE_URL`, plus a matching test —
without rewriting the existing entry point.
"""

SYSTEM_PROMPT = """\
You are a senior Node.js engineer regenerating one source file inside
the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The package root is `{service_subdir}/`. Source lives under `src/`.
- The package uses `"type": "module"` (ESM), so use `import` /
  `export` syntax — never `require`.
- The wrapper-shared `Config` lives in `src/config.js` and is already
  populated from `<wrapper>/.env` plus the local service `.env`. Read
  it via `import {{ config }} from './config.js';` (or
  `'../config.js'` from a subdirectory).
- The reference test (`src/index.test.js`) uses Node's built-in
  `node:test` runner and `node:assert`. Stick to those — do NOT pull
  in jest / mocha / vitest.
- Node 22 ships a stdlib `node:sqlite` module that exposes a synchronous
  `DatabaseSync` API. Use it for the SQL queries. NEVER add a
  `better-sqlite3` / `sqlite3` dependency to package.json.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The DB table for the new entity MUST be
  named `{items_plural}` (this matches the dev_skel shared-DB
  integration test convention).

Shared environment (CRITICAL — every backend service in the wrapper
relies on the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` — common database. Read it via `config.databaseUrl`
  (already populated by `src/config.js`). NEVER probe
  `process.env.DATABASE_URL` directly in handler code.
- `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_ISSUER` / `JWT_ACCESS_TTL` /
  `JWT_REFRESH_TTL` — exposed via `config.jwt.*`. NEVER hardcode the
  secret.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- ESM only (`import` / `export default`). 2-space indentation, single
  quotes, semicolons. Match the style of the REFERENCE files.
- Async/await everywhere; no callbacks.
- For sqlite path resolution: when `config.databaseUrl` starts with
  `sqlite:///`, strip the prefix and resolve the remaining path
  relative to the wrapper directory (one level above `src/`).
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `node --test src` after generation to confirm the new "
        "{item_class} module passes its tests. The wrapper-shared "
        "`<wrapper>/.env` is already wired in via `src/config.js`."
    ),
    "targets": [
        {
            "path": "src/{item_name}.js",
            "template": None,
            "language": "javascript",
            "description": "src/{item_name}.js — `{item_class}` CRUD helpers",
            "prompt": """\
Create `src/{item_name}.js` exposing CRUD helpers for the `{item_class}`
entity backed by the wrapper-shared SQLite database.

Required content:
- File header docblock: "CRUD helpers for the wrapper-shared
  `{items_plural}` table. Reads `DATABASE_URL` via the shared
  `config.databaseUrl` from `./config.js`."
- Imports:
  ```js
  import {{ DatabaseSync }} from 'node:sqlite';
  import {{ dirname, resolve }} from 'node:path';
  import {{ fileURLToPath }} from 'node:url';
  import {{ config }} from './config.js';
  ```
- A small private `resolveDbPath()` helper that:
  1. Reads `config.databaseUrl`.
  2. Returns `null` if it does not start with `sqlite://`.
  3. Strips the `sqlite:///` prefix and, when the remainder is
     relative, resolves it against the wrapper directory (one level
     above `src/`, derived from `import.meta.url`).
- A private `openDb()` helper that calls `resolveDbPath()` and
  returns a `new DatabaseSync(path)` (or throws when the URL is not
  sqlite).
- Three exports (all `async` for future-proofing even though the API
  is synchronous):
  - `export async function list{item_class}s()` —
    `SELECT id, name, description, is_completed, created_at,
    updated_at FROM {items_plural}` and return the rows as an
    array of plain objects.
  - `export async function get{item_class}(id)` — same SELECT plus
    `WHERE id = ?`. Return the row or `null` when missing.
  - `export async function create{item_class}({{ name, description,
    isCompleted = false }})` — `INSERT INTO {items_plural} (name,
    description, is_completed) VALUES (?, ?, ?)` and return the new
    row by re-selecting it via `lastInsertRowid`.
- Authentication: when `{auth_type}` is anything other than `none`,
  add a tiny `requireBearerToken(authHeader)` helper that:
  1. Throws `new Error('missing token')` when `authHeader` is empty
     or does not start with `Bearer `.
  2. Pulls the secret from `config.jwt.secret` and includes it in a
     comment as a placeholder for the real verification (production
     wiring is left to the user).
  Export it alongside the CRUD helpers and document that
  HTTP-binding code (Express / Fastify) is responsible for calling
  it before the mutating helpers.

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}.test.js",
            "template": "src/index.test.js",
            "language": "javascript",
            "description": "src/{item_name}.test.js — node:test suite",
            "prompt": """\
Create `src/{item_name}.test.js` mirroring the style of the REFERENCE
test file but exercising the new `{item_class}` helpers.

Required content:
- Imports:
  ```js
  import {{ test, before, after }} from 'node:test';
  import assert from 'node:assert';
  import {{ DatabaseSync }} from 'node:sqlite';
  import {{ tmpdir }} from 'node:os';
  import {{ mkdtempSync, rmSync }} from 'node:fs';
  import {{ join }} from 'node:path';
  ```
- A `before()` hook that:
  1. Creates a fresh tmp directory via `mkdtempSync(join(tmpdir(),
     'next-js-skel-test-'))`.
  2. Sets `process.env.DATABASE_URL = `sqlite:///` + the absolute
     path to a `db.sqlite3` file inside that tmp dir`.
  3. Opens the file with `DatabaseSync` and runs
     `CREATE TABLE {items_plural} (id INTEGER PRIMARY KEY
     AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
     is_completed INTEGER NOT NULL DEFAULT 0, created_at TEXT,
     updated_at TEXT);`.
- An `after()` hook that removes the tmp directory.
- Three test cases:
  - `'list{item_class}s returns empty array on fresh db'` — calls
    `list{item_class}s()` from `./{item_name}.js` and asserts the
    result is an empty array.
  - `'create{item_class} inserts and returns the row'` — calls
    `create{item_class}({{ name: 'Test {item_class}', description:
    'hi' }})` and asserts the returned object has `id`, `name`,
    `description` set.
  - `'get{item_class} fetches by id'` — creates a row, calls
    `get{item_class}(id)` and asserts the result matches.

Notes:
- Re-import `./{item_name}.js` AFTER setting `process.env.DATABASE_URL`
  so the helper picks it up. Use `await import('./{item_name}.js')`
  inside each test rather than a top-level static import.
- The REFERENCE test below uses node:test + node:assert; match its
  style.

REFERENCE (`src/index.test.js`):
---
{template}
---
""",
        },
    ],
}
