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


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Node.js engineer integrating a freshly generated
Next.js 15 App Router service into an existing dev_skel multi-service
wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`next-js-skel`). It already ships:
- The wrapper-shared `Item` model + API route at `/api/items` using
  better-sqlite3 against the shared `DATABASE_URL`.
- The wrapper-shared `ReactState` model + API routes at `/api/state`
  and `/api/state/[key]`.
- A user-chosen `{item_class}` model + API routes (the per-target
  manifest rewrote `Item` to `{item_class}` for this run).
- JWT auth via `jose` — the secret comes from
  `process.env.JWT_SECRET` (the wrapper-shared secret — NEVER
  hardcode it).
- The wrapper-shared `<wrapper>/.env` is loaded by `src/config.js`
  so `DATABASE_URL` and the JWT vars are identical to every other
  backend in the project.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A sibling client module (CJS, `require`/`module.exports`) for each
   sibling backend the new service should call. The client must read
   the sibling's URL from `process.env.SERVICE_URL_<UPPER_SLUG>` so
   it picks up the auto-allocated port from `_shared/service-urls.env`
   without any per-deployment edits.
2. Integration tests (`src/lib/integration.test.js`) using Node's
   built-in `node:test` + `node:assert` that exercise the cross-service
   flows end-to-end via the wrapper-shared SQLite database (and, when
   sibling backends are present, via the typed clients above).

Coding rules:
- Use global `fetch` (Node 18+) for sibling HTTP calls. Do NOT add
  `axios`, `node-fetch`, `got`, or any other HTTP client dependency.
- Sibling client files use **CJS** (`require` / `module.exports`) so
  they can be loaded from both ESM and CJS contexts.
- Read JWT material via `process.env.JWT_SECRET` /
  `process.env.JWT_ALGORITHM` etc. NEVER hardcode the secret.
- Use Node's built-in `node:test` runner and `node:assert` for tests.
  Do NOT use jest / mocha / vitest.
- Guard sibling calls with `try/catch` — when the env var is missing
  or the service is unreachable, call `test.skip()` or print a skip
  message and return early.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items` and
  `/api/{items_plural}` endpoints. Do not assume sibling services
  exist; gracefully degrade.

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
        "Integration phase: writes src/lib/sibling-clients.js and "
        "src/lib/integration.test.js, then runs the test-and-fix loop "
        "via `npm test`."
    ),
    "test_command": "npm test",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "src/lib/sibling-clients.js",
            "language": "javascript",
            "description": "src/lib/sibling-clients.js — CJS HTTP clients for sibling backends",
            "prompt": """\
Write `src/lib/sibling-clients.js`. The module exports one typed
client class per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- **CJS module** — use `require` / `module.exports`. Do NOT use
  `import` / `export` syntax.
- Use global `fetch` (Node 18+) for HTTP calls. Do NOT add any HTTP
  client dependency to package.json.
- Each sibling backend gets a class named `<PascalSlug>Client`
  (e.g. `WebUiClient`, `AuthApiClient`). The class:
    - Reads its base URL from
      `process.env.SERVICE_URL_<UPPER_SLUG>` in the constructor.
      Throws an `IntegrationError` with a clear message when the env
      var is missing.
    - Accepts an optional `token` parameter; when set, every request
      sends `Authorization: Bearer <token>`.
    - Exposes `async listItems()` and `async getState(key)` methods
      that hit the sibling's wrapper-shared `/api/items` and
      `/api/state/<key>` endpoints. Return parsed JSON objects.
    - Throws `IntegrationError` on non-2xx responses, with the status
      code and response body.
- Define an `IntegrationError` class extending `Error` at the top of
  the file with `statusCode` and `responseBody` properties.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationError` class and export it with
  `module.exports = {{ IntegrationError }};`. Do NOT define dummy
  client classes for non-existent siblings.

Output the full file contents only.
""",
        },
        {
            "path": "src/lib/integration.test.js",
            "language": "javascript",
            "description": "src/lib/integration.test.js — cross-service node:test cases",
            "prompt": """\
Write `src/lib/integration.test.js`. Integration tests using `node:test`
+ `node:assert` that exercise the new `{service_label}` service
end-to-end and (when sibling backends are present) verify the
cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use Node's built-in `node:test` (`describe`, `it`, `before`,
  `after`) and `node:assert`. Do NOT use jest / mocha / vitest.
- Guard sibling client calls with `try/catch` — when the env var is
  missing or the service is unreachable, print a skip message and
  return early (or use `test.skip()`).
- Use `better-sqlite3` or the `node:sqlite` `DatabaseSync` API for
  direct DB assertions (whichever is available in the project).

Required tests:

1. `test items endpoint round trip` — use the DB directly to insert
   an `Item` row into the `items` table, then query and assert the
   row exists.

2. `test react state round trip` — insert a react_state row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `test {items_plural} endpoint uses jwt` — read
   `process.env.JWT_SECRET` and assert it is a non-empty string.

4. `test jwt secret is wrapper shared` — assert that
   `process.env.JWT_SECRET` is defined and non-empty.

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `test sibling <slug> items visible via shared db`.
   Guard instantiation like this:
   ```js
   let client;
   try {{
       const {{ <PascalSlug>Client }} = require('./sibling-clients');
       client = new <PascalSlug>Client();
   }} catch (e) {{
       console.log('SKIP: SERVICE_URL_<SLUG> not set');
       return;
   }}
   ```
   Then call `await client.listItems()` inside `try/catch` and skip
   if unreachable.

6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Imports:
- `const {{ describe, it, before, after }} = require('node:test');`
- `const assert = require('node:assert');`
- (when {sibling_count} > 0)
  `const {{ IntegrationError, ... }} = require('./sibling-clients');`

Output the full file contents only.
""",
        },
    ],
}
