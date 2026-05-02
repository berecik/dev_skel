"""AI manifest for the ``next-js-ddd-skel`` skeleton.

This manifest exists separately from ``next-js-skel.py`` because the
two skeletons disagree on **where source files live**, even though
their HTTP contract is identical.

- ``next-js-skel`` (flat) keeps every CRUD handler in
  ``src/app/api/<resource>/`` directly, with helper functions in a
  small flat ``src/<resource>.js`` module.
- ``next-js-ddd-skel`` follows the canonical FastAPI shape: each
  resource is a self-contained module under ``src/<resource>/`` with
  the five-file split ``repository.js`` / ``adapters/sql.js`` /
  ``service.js`` / ``depts.js`` / ``routes.js``. App Router files
  under ``src/app/api/<resource>/`` are thin wire-up only; they
  build the service via ``depts.build<ItemClass>Service(db)``,
  authenticate via ``auth/middleware.requireAuth``, and call the
  route functions exported from ``src/<resource>/routes.js``.
  Routes never touch the DB; services take a Repository (never a
  Drizzle ``db`` handle); the adapter is the only file that
  imports ``../../lib/schema.js`` for that resource. Domain errors
  flow through ``shared/errors.DomainError`` and the
  ``wrapResponse`` HOF in ``shared/httpx.js`` translates them to
  JSON.

Re-using the flat manifest produced AI output that landed in the
wrong place: it wrote ``src/<item_name>.js`` (which does not exist
in the DDD layout) and tried to extend the App Router routes
inline. This file replaces that stub with a DDD-aware prompt set.

See ``_docs/DDD-SKELETONS.md`` for the cross-stack DDD layer rules.
"""

SYSTEM_PROMPT = """\
You are a senior Node.js / Next.js engineer regenerating one source
file inside the dev_skel `{skeleton_name}` skeleton. This skeleton
uses the canonical FastAPI shape adapted to Next.js: every CRUD
resource is a self-contained module under `src/<resource>/` with a
fixed five-file split, plus thin App Router wire-up files under
`src/app/api/<resource>/` that import from the resource module.

Project layout (CRITICAL — read carefully):
- The package root is `{service_subdir}/`. Source lives under `src/`.
- The package uses `"type": "module"` is NOT set; the codebase mixes
  CommonJS for the resource modules (`require` / `module.exports`)
  and ESM for App Router route files (`import` / `export`). Match
  the style of the REFERENCE file you are rewriting — when the
  reference uses `require`/`module.exports`, do the same; when it
  uses `import`/`export`, do the same.
- The entry point is filesystem-routed: Next.js App Router files
  under `src/app/api/<resource>/route.js` (and
  `src/app/api/<resource>/[id]/route.js`) auto-mount endpoints. There
  is NO single composition root to edit — App Router wires routes
  via filesystem layout.
- Every resource module follows this layout:
    src/<resource>/
      repository.js       -- abstract repo contract + assert<Class>Repository(repo)
      adapters/sql.js     -- Drizzle implementation (the ONLY file in this
                             resource that imports ../../lib/schema.js)
      service.js          -- business logic, takes a Repository
      depts.js            -- composition root: build<ItemClass>Service(db)
      routes.js           -- exports thin route functions
                             (getList/postCreate/getOne/patchUpdate/deleteOne[/postComplete])
- The new resource being added is `src/{item_name}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The Drizzle entities for this run are
  consolidated in `src/lib/schema.js` -- assume the
  `{items_plural}` Drizzle table already exists there.

Layer rules (NON-NEGOTIABLE):
1. App Router route files under `src/app/api/{items_plural}/` are
   thin wire-up only. They build the service via
   `build{item_class}Service(db)`, authenticate via
   `requireAuth(req, deps)` (from `auth/middleware`) -- but in
   practice authentication runs INSIDE the route functions exported
   from `src/{item_name}/routes.js`, so the App Router file just
   imports the route function, builds the service via
   `wireService(build{item_class}Service)`, and wraps each export
   with `wrapResponse(...)` from `shared/httpx`.
2. Services take a Repository (duck-typed; the abstract
   `assert{item_class}Repository(repo)` checker enforces it at
   construction time), NEVER a Drizzle `db` handle.
3. The adapter is the ONLY file in this resource that imports
   `../../lib/schema.js`. Other files use the abstract repository.
4. DTOs are explicit and use **snake_case keys** (e.g.
   `is_completed`, `category_id`, `created_at`, `updated_at`). Do
   NOT return raw Drizzle results to consumers without shape
   control; the Drizzle row already uses snake_case columns so a
   plain spread is fine, but never invent camelCase keys.
5. Domain errors flow through `shared/errors.DomainError`. Throw
   one of the convenience factories (`DomainError.notFound(...)`,
   `DomainError.validation(...)`, `DomainError.conflict(...)`,
   `DomainError.unauthorized(...)`); the `wrapResponse` HOF
   translates them to JSON with the right status.
6. `depts.js` is the only place that wires adapter -> service.

Available shared helpers from `src/shared/`:
- `errors.js` (CJS):
  * `DomainError` class with `kind` field; static factories
    `DomainError.notFound(msg)`, `DomainError.conflict(msg)`,
    `DomainError.validation(msg)`, `DomainError.unauthorized(msg)`,
    `DomainError.forbidden(msg)`, `DomainError.other(msg)`.
  * `wrapDb(err)` -- maps low-level driver errors to DomainError
    (unique-constraint -> Conflict; SyntaxError -> Validation).
  * `KINDS` constant array.
- `httpx.js` (CJS):
  * `jsonError(status, detail)` -- builds a `NextResponse.json({error}, {status})`.
  * `wrapResponse(handler)` -- HOF: `(handler) => (request, ctx) =>`
    a wrapper that catches DomainErrors and returns the matching
    JSON envelope. Routes use this verbatim.
  * `toResponse(err)`, `STATUS_FOR_KIND`.
- `wire.js` (CJS):
  * `getDb()` re-export + `getDeps()` returning
    `{ userRepository }` (memoized against the singleton db).
  * `wireService(builder)` -- memoizes a per-service factory
    against the singleton db; call the returned function with no
    arguments inside each App Router export to retrieve the
    service instance.
- `repository.js` (CJS):
  * `Repository` (throwing-stub superclass), `AbstractUnitOfWork`.
  * `assertHasMethods(repo, names, label)` -- throws if `repo`
    misses any named method. The resource's `repository.js` calls
    this from `assert{item_class}Repository(repo)`.

Auth (JWT, flat module under `src/auth/`):
- `auth/middleware.js` exports
  `async requireAuth(request, deps = {{}}) -> Promise<{{ sub, username, ... }}>`
  which throws `DomainError.unauthorized(...)` on failure. Pass
  `{{ userRepository }}` (the user repo from
  `users/adapters/sql.js`) when the route needs to resolve the
  full user row, otherwise pass an empty object.
- The per-resource `routes.js` files call `requireAuth(request, deps)`
  internally; the App Router wire-up just supplies the `deps` via
  `getDeps()` from `shared/wire`.

Drizzle conventions (adapters/sql.js only):
- Import the table from `'../../lib/schema'` (e.g.
  `const {{ {items_plural} }} = require('../../lib/schema');`).
- Use `db.select().from(table).all()`, `db.insert(table).values({{...}}).returning().get()`,
  `db.update(table).set({{...}}).where(eq(table.id, n)).returning().get()`,
  `db.delete(table).where(eq(table.id, n)).run()`.
- Datetime columns use Drizzle's `integer({{ mode: 'timestamp' }})`
  -- pass JavaScript `Date` objects when setting them
  (e.g. `updated_at: new Date()`); Drizzle stores them as unix
  millis but reads them back as `Date` objects.
- Wrap driver errors with `wrapDb(err)` from `../../shared/errors`
  inside `create` / `update` so unique-constraint violations
  surface as `DomainError.conflict(...)`.

JSON shape (wrapper-shared contract):
- All keys are `snake_case` (`is_completed`, `category_id`,
  `created_at`, `updated_at`). Foreign keys land as `category_id`,
  not `category`.
- Datetimes serialise via the default `JSON.stringify(Date)` which
  produces ISO 8601 strings.
- Optional / nullable FKs are passed as `null` (not `undefined`).

Shared environment (every backend service in the wrapper relies on
the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` -- common database. Resolved via `src/config.js`
  (`config.databaseUrl`); the Drizzle handle in `src/lib/db.js`
  consumes it. NEVER probe `process.env.DATABASE_URL` from a
  resource module.
- `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_ISSUER` / `JWT_ACCESS_TTL`
  / `JWT_REFRESH_TTL` -- exposed via `config.jwt.*`. NEVER hardcode
  the secret; resource code does not read JWT material directly --
  `auth/middleware.requireAuth` and `lib/auth.js` do that for you.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- 2-space indentation, single quotes, semicolons. Match the style
  of the REFERENCE files exactly.
- Async/await everywhere; no callbacks.
- The Drizzle better-sqlite3 driver is synchronous, so service
  methods don't need to be `async` -- but match what the REFERENCE
  shows (the items service uses synchronous methods).
- App Router route files use ESM (`import` / `export`). Resource
  modules use CJS (`require` / `module.exports`). DO NOT mix.
- When `{auth_type}` is `none`, the routes file may skip the
  `requireAuth(request, deps)` call (or call it as a no-op); the
  rest of the layout stays the same.
- Do NOT introduce new dependencies.
- Output ONLY the file's contents. No markdown fences, no
  commentary.
"""


MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `npm test` after generation to confirm the new "
        "src/{item_name}/ module passes its tests. The wrapper-shared "
        "<wrapper>/.env is wired in via src/config.js; the Drizzle "
        "{items_plural} entity in src/lib/schema.js is assumed to "
        "already exist."
    ),
    "targets": [
        {
            "path": "src/{item_name}/repository.js",
            "template": "src/items/repository.js",
            "language": "javascript",
            "description": (
                "src/{item_name}/repository.js -- abstract Repository "
                "contract for `{item_class}`"
            ),
            "prompt": """\
Create `src/{item_name}/repository.js` for the `{item_class}` resource.

This file documents the Repository contract every implementation must
satisfy and exports a runtime checker
`assert{item_class}Repository(repo)` that throws if a method is
missing. It does NOT import `../../lib/schema.js` -- only the adapter
under `adapters/sql.js` does that.

Required contents:
- File header docblock describing the `{item_class}Repository`
  contract. List the methods (mirroring the reference):
    - `list()`        -> {item_class}[]
    - `get(id)`       -> {item_class} | null
    - `create(dto)`   -> {item_class}
    - `update(id, patch)` -> {item_class} | null
    - `delete(id)`    -> boolean (true on success)
  Document the entity row shape: `{{ id, name, description,
  is_completed, category_id, owner_id, created_at, updated_at }}`
  (or whatever the Drizzle table for `{items_plural}` exposes --
  match snake_case column names).
- CJS imports:
  ```js
  const {{ assertHasMethods }} = require('../shared/repository');
  ```
- A `REQUIRED_METHODS` array listing every method name as a string:
  `['list', 'get', 'create', 'update', 'delete']`.
- A function:
  ```js
  function assert{item_class}Repository(repo) {{
    assertHasMethods(repo, REQUIRED_METHODS, '{item_class}Repository');
  }}
  ```
- Export both via:
  ```js
  module.exports = {{ assert{item_class}Repository, REQUIRED_METHODS }};
  ```

REFERENCE (`src/items/repository.js` -- adapt every line for
`{item_class}`, preserving the docblock structure and the
assertHasMethods plumbing):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/adapters/sql.js",
            "template": "src/items/adapters/sql.js",
            "language": "javascript",
            "description": (
                "src/{item_name}/adapters/sql.js -- Drizzle implementation "
                "of {item_class}Repository"
            ),
            "prompt": """\
Create `src/{item_name}/adapters/sql.js`. This is the ONLY file in
the `{item_name}` resource that imports from `../../lib/schema.js`.

Required contents:
- File header docblock: "Drizzle-backed implementation of
  {item_class}Repository."
- CJS imports (match the reference exactly):
  ```js
  const {{ eq }} = require('drizzle-orm');
  const {{ {items_plural} }} = require('../../lib/schema');
  const {{ wrapDb }} = require('../../shared/errors');
  ```
- `class Drizzle{item_class}Repository {{`
    - `constructor(db)` -- throws if `db` is missing, stores
      `this.db = db`.
    - `list()` -- `return this.db.select().from({items_plural}).all();`.
    - `get(id)` -- `return this.db.select().from({items_plural}).where(eq({items_plural}.id, Number(id))).get() || null;`.
    - `create(dto)` -- `db.insert({items_plural}).values({{...}}).returning().get()`. Wrap with
      `try {{ ... }} catch (err) {{ throw wrapDb(err); }}`.
      Pass through fields explicitly; default optional fields:
      `description: dto.description ?? null`,
      `is_completed: Boolean(dto.is_completed)`,
      `category_id: dto.category_id ?? null`,
      `owner_id: dto.owner_id ?? null`. Adapt the field list to
      whatever fields `{item_class}` actually has.
    - `update(id, patch)` -- fetch existing via `this.get(itemId)`;
      return `null` when missing; merge non-undefined patch fields
      onto the existing row; set `updated_at: new Date()`;
      `db.update({items_plural}).set(next).where(eq({items_plural}.id, itemId)).returning().get()`. Wrap with `try/catch -> wrapDb`.
    - `delete(id)` -- fetch existing; return `false` when missing;
      `db.delete({items_plural}).where(eq({items_plural}.id, itemId)).run()`; return `true`.
- `module.exports = {{ Drizzle{item_class}Repository }};`

The `{items_plural}` Drizzle table is assumed to already exist in
`src/lib/schema.js` -- do NOT add or modify it here.

REFERENCE (`src/items/adapters/sql.js` -- adapt every line for
`{item_class}`, preserving the structure, error wrapping, and
import ordering):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/service.js",
            "template": "src/items/service.js",
            "language": "javascript",
            "description": (
                "src/{item_name}/service.js -- business logic over "
                "{item_class}Repository"
            ),
            "prompt": """\
Create `src/{item_name}/service.js`. This is the resource's
business-logic layer. It depends only on the abstract Repository
(verified at construction time via `assert{item_class}Repository`).

Required contents:
- File header docblock matching the reference's tone: "{item_class}Service
  -- pure domain logic, framework-agnostic." Mention that it throws
  `DomainError` on expected failure modes so route layers can map
  to HTTP statuses.
- CJS imports:
  ```js
  const {{ DomainError }} = require('../shared/errors');
  const {{ assert{item_class}Repository }} = require('./repository');
  ```
- `class {item_class}Service {{`
    - `constructor(repo)` -- calls `assert{item_class}Repository(repo)`,
      stores `this.repo = repo`.
    - `list()` -- `return this.repo.list();`.
    - `get(id)` -- delegate; throw
      `DomainError.notFound('{item_class} not found')` when null.
    - `create(dto)` -- validate `dto.name` is a non-empty string
      (or whichever required field `{item_class}` has); throw
      `DomainError.validation('name is required')` on bad input.
      Forward the DTO to `this.repo.create(...)` with explicit
      snake_case keys (`description`, `is_completed`, `category_id`,
      `owner_id`).
    - `update(id, patch)` -- `const updated = this.repo.update(id, patch || {{}}); if (!updated) throw DomainError.notFound(...); return updated;`
    - `delete(id)` -- `if (!this.repo.delete(id)) throw DomainError.notFound(...);`
- `module.exports = {{ {item_class}Service }};`

DTOs are explicit -- never return raw Drizzle results without
shape control. Snake_case keys throughout
(`is_completed`, `category_id`, `created_at`, `updated_at`).

REFERENCE (`src/items/service.js`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/depts.js",
            "template": "src/items/depts.js",
            "language": "javascript",
            "description": (
                "src/{item_name}/depts.js -- composition root "
                "wiring adapter -> service"
            ),
            "prompt": """\
Create `src/{item_name}/depts.js`. This is the ONLY place in the
resource that wires the adapter into the service.

Required contents:
- File header docblock matching the reference's tone (explains why
  routes import `build{item_class}Service(db)` from here so they
  never reach for the adapter directly).
- CJS imports:
  ```js
  const {{ Drizzle{item_class}Repository }} = require('./adapters/sql');
  const {{ {item_class}Service }} = require('./service');
  ```
- `function build{item_class}Repository(db)` -- returns
  `new Drizzle{item_class}Repository(db)`.
- `function build{item_class}Service(db)` -- returns
  `new {item_class}Service(build{item_class}Repository(db))`.
- `module.exports = {{ build{item_class}Repository, build{item_class}Service }};`

Match the reference verbatim except for the entity / class names.

REFERENCE (`src/items/depts.js`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/routes.js",
            "template": "src/items/routes.js",
            "language": "javascript",
            "description": (
                "src/{item_name}/routes.js -- thin route functions "
                "for /api/{items_plural}"
            ),
            "prompt": """\
Create `src/{item_name}/routes.js`. This file exports thin route
functions consumed by the App Router wire-up under
`src/app/api/{items_plural}/`. It NEVER imports
`../../lib/schema.js` -- only the adapter does.

Required contents:
- File header docblock: "HTTP route handlers for /api/{items_plural}.
  Each handler is a `(request, ctx) => Response`."
- CJS imports (mirror the reference exactly):
  ```js
  const {{ NextResponse }} = require('next/server');
  const {{ DomainError }} = require('../shared/errors');
  const {{ requireAuth }} = require('../auth/middleware');
  ```
- A private `async function readJsonBody(request)` helper that
  calls `await request.json()` and re-throws as
  `DomainError.validation('Invalid JSON body')` on parse failure
  (mirror the reference verbatim).
- Five exported route-builder functions, each taking
  `(service, deps)` and returning an async handler
  `(request, ctx) => Response`:
    - `function getList(service, deps)` -- `await requireAuth(request, deps); const rows = service.list(); return NextResponse.json(rows);`.
    - `function postCreate(service, deps)` -- `await requireAuth`;
      read body; if `{auth_type}` is not `none`, derive
      `ownerId = user && user.sub ? Number(user.sub) : null`;
      call `service.create({{ name, description, is_completed,
      category_id, owner_id }})`; return `NextResponse.json(created, {{ status: 201 }})`.
    - `function getOne(service, deps)` -- `await requireAuth`;
      `const params = await ctx.params;`;
      `service.get(params.id)`; `NextResponse.json(row)`.
    - `function patchUpdate(service, deps)` -- `await requireAuth`;
      `const params = await ctx.params;`; read body;
      `service.update(params.id, body)`; `NextResponse.json(updated)`.
    - `function deleteOne(service, deps)` -- `await requireAuth`;
      `const params = await ctx.params;`; `service.delete(params.id);`;
      `return new NextResponse(null, {{ status: 204 }});`.
- IF the entity supports a complete-toggle action (the canonical
  `Item` does -- check whether `{item_class}` retains the
  `is_completed` semantics): also export
  `function postComplete(service, deps)` that calls
  `service.complete(params.id)` and returns `NextResponse.json(updated)`.
  Skip this when `{item_class}` semantics make the toggle
  meaningless -- in doubt, INCLUDE it (it mirrors the reference
  and the App Router file under `[id]/complete/route.js` will
  expect it).
- Module export listing every function:
  ```js
  module.exports = {{ getList, postCreate, getOne, patchUpdate, deleteOne, postComplete }};
  ```
  (Drop `postComplete` from the list if you decided to skip it.)

When `{auth_type}` is `none`, you may keep the `requireAuth`
calls (they will succeed with a no-op token check) OR drop them
-- match whatever the user asked for via `{auth_details}`.

REFERENCE (`src/items/routes.js` -- preserve the handler structure,
the `readJsonBody` helper, the `await ctx.params` idiom, and the
`NextResponse.json(...)` envelope shape):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/app/api/{items_plural}/route.js",
            "template": "src/app/api/items/route.js",
            "language": "javascript",
            "description": (
                "src/app/api/{items_plural}/route.js -- App Router "
                "list/create wire-up"
            ),
            "prompt": """\
Create `src/app/api/{items_plural}/route.js`. This is the App Router
wire-up for the list (`GET /api/{items_plural}`) and create
(`POST /api/{items_plural}`) endpoints. It is THIN: it just builds
the service via `wireService(build{item_class}Service)` and wraps
each route function from `src/{item_name}/routes.js` with
`wrapResponse`.

Required contents:
- File header docblock: "/api/{items_plural} -- thin wire-up around
  the {item_name} service."
- ESM imports (this file uses `import` / `export`, NOT `require` --
  match the reference exactly):
  ```js
  import {{ wrapResponse }} from '../../../shared/httpx';
  import {{ getDeps, wireService }} from '../../../shared/wire';
  import {{ build{item_class}Service }} from '../../../{item_name}/depts';
  import * as {item_name}Routes from '../../../{item_name}/routes';
  ```
- `const {item_name} = wireService(build{item_class}Service);`
- Two exports:
  ```js
  export const GET = wrapResponse((req, ctx) => {item_name}Routes.getList({item_name}(), getDeps())(req, ctx));
  export const POST = wrapResponse((req, ctx) =>
    {item_name}Routes.postCreate({item_name}(), getDeps())(req, ctx),
  );
  ```

Match the reference exactly except for the entity / variable names.

REFERENCE (`src/app/api/items/route.js`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/app/api/{items_plural}/[id]/route.js",
            "template": "src/app/api/items/[id]/route.js",
            "language": "javascript",
            "description": (
                "src/app/api/{items_plural}/[id]/route.js -- App Router "
                "get/update/delete wire-up"
            ),
            "prompt": """\
Create `src/app/api/{items_plural}/[id]/route.js`. This is the App
Router wire-up for the per-id endpoints (`GET`, `PATCH`, `DELETE`).
The path is one level deeper than the list route, so the relative
import paths gain ONE extra `../` segment compared to
`src/app/api/{items_plural}/route.js`.

Required contents:
- File header docblock: "/api/{items_plural}/[id] -- thin wire-up
  around the {item_name} service."
- ESM imports (note the FOUR `../` segments to reach `shared/`,
  `{item_name}/`, etc.):
  ```js
  import {{ wrapResponse }} from '../../../../shared/httpx';
  import {{ getDeps, wireService }} from '../../../../shared/wire';
  import {{ build{item_class}Service }} from '../../../../{item_name}/depts';
  import * as {item_name}Routes from '../../../../{item_name}/routes';
  ```
- `const {item_name} = wireService(build{item_class}Service);`
- Three exports:
  ```js
  export const GET = wrapResponse((req, ctx) => {item_name}Routes.getOne({item_name}(), getDeps())(req, ctx));
  export const PATCH = wrapResponse((req, ctx) =>
    {item_name}Routes.patchUpdate({item_name}(), getDeps())(req, ctx),
  );
  export const DELETE = wrapResponse((req, ctx) =>
    {item_name}Routes.deleteOne({item_name}(), getDeps())(req, ctx),
  );
  ```

Match the reference exactly except for the entity / variable names.

REFERENCE (`src/app/api/items/[id]/route.js`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/app/api/{items_plural}/[id]/complete/route.js",
            "template": "src/app/api/items/[id]/complete/route.js",
            "language": "javascript",
            "description": (
                "src/app/api/{items_plural}/[id]/complete/route.js -- App "
                "Router complete-toggle wire-up"
            ),
            "prompt": """\
Create `src/app/api/{items_plural}/[id]/complete/route.js`. This is
the App Router wire-up for the complete-toggle endpoint (`POST`).
The path is two levels deeper than the list route, so the relative
import paths gain TWO extra `../` segments.

Only emit this file when `src/{item_name}/routes.js` exports a
`postComplete` function (which mirrors the canonical `Item.complete`
toggle). When the entity has no completion semantics, you may emit
a comment-only file:

```js
/* No complete-toggle action for `{item_class}` -- this stub keeps
 * the App Router happy when re-running the generator on an
 * existing tree. Delete this file if it is not needed. */
```

For the canonical case, required contents:
- File header docblock: "/api/{items_plural}/[id]/complete -- thin
  wire-up around the {item_name} service."
- ESM imports (note the FIVE `../` segments to reach `shared/`):
  ```js
  import {{ wrapResponse }} from '../../../../../shared/httpx';
  import {{ getDeps, wireService }} from '../../../../../shared/wire';
  import {{ build{item_class}Service }} from '../../../../../{item_name}/depts';
  import * as {item_name}Routes from '../../../../../{item_name}/routes';
  ```
- `const {item_name} = wireService(build{item_class}Service);`
- One export:
  ```js
  export const POST = wrapResponse((req, ctx) =>
    {item_name}Routes.postComplete({item_name}(), getDeps())(req, ctx),
  );
  ```

Match the reference exactly except for the entity / variable names.

REFERENCE (`src/app/api/items/[id]/complete/route.js`):
---
{template}
---

Output only the file's contents.
""",
        },
    ],
}


# --------------------------------------------------------------------------- #
#  Integration manifest (second Ollama session)
# --------------------------------------------------------------------------- #
#
# After the per-target MANIFEST above generates the new resource module,
# ``_bin/skel-gen-ai`` runs a second Ollama pass against the block below
# to add cross-service clients + integration tests. The shape mirrors
# ``next-js-skel.py``'s integration manifest but with paths and prompt
# text updated for the DDD layout (no flat ``src/<item_name>.js`` -- we
# describe the per-resource module convention instead).


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Node.js / Next.js engineer integrating a freshly
generated Next.js 15 App Router service into an existing dev_skel
multi-service wrapper. The service uses the DDD per-resource layout:
each CRUD resource lives under `src/<resource>/` with the five-file
split (repository / adapters/sql / service / depts / routes), and
App Router files under `src/app/api/<resource>/` are thin wire-up.

The new service is `{service_label}` (slug `{service_slug}`, tech
`next-js-ddd-skel`). It already ships:
- The wrapper-shared `Item` resource at `src/items/` mounted at
  `/api/items` (see the reference resource module for the canonical
  layout).
- Wrapper-shared `Category`, `Order`, `Catalog`, and `State`
  resources, each in its own `src/<resource>/` module.
- A user-chosen `{item_class}` module under `src/{item_name}/`
  mounted at `/api/{items_plural}` (the per-target manifest added
  it).
- JWT auth via `src/auth/` -- `requireAuth(request, deps)` from
  `auth/middleware.js`. The JWT secret comes from `config.jwt.secret`
  (the wrapper-shared secret -- NEVER hardcode it).
- The wrapper-shared `<wrapper>/.env` is loaded by `src/config.js`
  so `DATABASE_URL` and the JWT vars are identical to every other
  backend in the project.
- DB driver is Drizzle on top of `better-sqlite3`. No raw `sqlite3`
  / `node:sqlite` queries in resource code.
- Domain errors flow through `shared/errors.DomainError` and
  `shared/httpx.wrapResponse` translates them to JSON.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A sibling client module (CJS, `require` / `module.exports`) for
   each sibling backend the new service should call. The client must
   read the sibling's URL from `process.env.SERVICE_URL_<UPPER_SLUG>`
   so it picks up the auto-allocated port from
   `_shared/service-urls.env` without any per-deployment edits.
2. Integration tests (`src/lib/integration.test.js`) using Node's
   built-in `node:test` + `node:assert` that exercise the cross-service
   flows end-to-end via the wrapper-shared SQLite database (and, when
   sibling backends are present, via the typed clients above).

Coding rules:
- Use global `fetch` (Node 18+) for sibling HTTP calls. Do NOT add
  `axios`, `node-fetch`, `got`, or any other HTTP client dependency.
- Sibling client files use **CJS** (`require` / `module.exports`) so
  they can be loaded from both ESM and CJS contexts.
- Read JWT material via `config.jwt.*` (or `process.env.JWT_SECRET`
  in tests). NEVER hardcode the secret.
- Use Node's built-in `node:test` runner and `node:assert` for tests.
  Do NOT use jest / mocha / vitest.
- Guard sibling calls with `try/catch` -- when the env var is missing
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
            "description": (
                "src/lib/sibling-clients.js -- CJS HTTP clients for "
                "sibling backends"
            ),
            "prompt": """\
Write `src/lib/sibling-clients.js`. The module exports one typed
client class per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- **CJS module** -- use `require` / `module.exports`. Do NOT use
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
    - Throws `IntegrationError` on non-2xx responses, with the
      status code and response body.
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
            "description": (
                "src/lib/integration.test.js -- cross-service node:test "
                "cases"
            ),
            "prompt": """\
Write `src/lib/integration.test.js`. Integration tests using
`node:test` + `node:assert` that exercise the new `{service_label}`
service end-to-end and (when sibling backends are present) verify
the cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use Node's built-in `node:test` (`describe`, `it`, `before`,
  `after`) and `node:assert`. Do NOT use jest / mocha / vitest.
- Guard sibling client calls with `try/catch` -- when the env var
  is missing or the service is unreachable, print a skip message
  and return early (or use `test.skip()`).
- Use `better-sqlite3` (or the Drizzle handle exposed via
  `src/lib/db.js`) for direct DB assertions.
- The new resource lives at `src/{item_name}/` and its service
  factory is exported as `build{item_class}Service(db)` from
  `src/{item_name}/depts.js`.

Required tests:

1. `test items endpoint round trip` -- use the DB directly to insert
   an `Item` row into the `items` table, then query and assert the
   row exists.

2. `test react state round trip` -- insert a `state` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `test {items_plural} endpoint uses jwt` -- read
   `process.env.JWT_SECRET` and assert it is a non-empty string.

4. `test jwt secret is wrapper shared` -- assert that
   `process.env.JWT_SECRET` is defined and non-empty.

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `test sibling <slug> items visible via shared db`. Guard
   instantiation like this:
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
