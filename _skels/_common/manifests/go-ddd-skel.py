"""AI manifest for the ``go-ddd-skel`` skeleton.

This manifest exists separately from ``go-skel.py`` because the two
skeletons disagree on **where source files live**, even though their
HTTP contract is identical.

- ``go-skel`` (flat) keeps every CRUD handler in
  ``internal/handlers/<entity>.go`` as methods on a ``Deps`` struct,
  with one shared ``handlers.Register`` wiring routes inline.
- ``go-ddd-skel`` follows the canonical FastAPI shape: each resource
  is a self-contained module under ``internal/<resource>/`` with the
  five-file split ``models.go`` / ``repository.go`` /
  ``adapters/sql.go`` / ``service.go`` / ``depts.go`` / ``routes.go``.
  Routes never touch the DB; services take a ``Repository`` interface
  (never ``*gorm.DB``); the adapter is the only file that imports
  ``gorm.io/gorm`` for that resource. Domain errors flow as
  ``fmt.Errorf("%w: ...", shared.ErrNotFound)`` and ``routes.go``
  translates them via ``errors.Is``.

Re-using the flat manifest produced AI output that landed in the
wrong place: it created ``internal/handlers/<item>.go`` (which does
not exist in the DDD layout) and tried to extend a ``Register``
function that does not exist either. This file replaces that stub
with a DDD-aware prompt set.

See ``_docs/DDD-SKELETONS.md`` for the cross-stack DDD layer rules.
"""

SYSTEM_PROMPT = """\
You are a senior Go engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton. This skeleton uses the canonical
FastAPI shape: every CRUD resource is a self-contained module under
`internal/<resource>/` with a fixed five-file split.

Project layout (CRITICAL — read carefully):
- The Go module path is `github.com/example/go-ddd-skel`. NEVER use
  `github.com/example/go-skel` (that is a different, flat skeleton).
- The Go module root is `{service_subdir}/`. Source lives there plus
  `internal/` for private packages.
- The entry point is `main.go` — a slim composition root that calls
  each resource's `depts` provider then `RegisterRoutes`.
- Every resource module follows this layout:
    internal/<resource>/
      models.go            -- DTO types only (json:"snake_case" tags)
      repository.go        -- abstract interface
      adapters/sql.go      -- GORM implementation (only file importing gorm.io/gorm)
      service.go           -- business logic, takes a Repository
      depts.go             -- composition root: NewServiceFromDB(*gorm.DB) *Service
      routes.go            -- HTTP layer: pulls service, never touches DB
- The new resource being added is `internal/{item_name}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).

Layer rules (NON-NEGOTIABLE):
1. Routes never touch the DB. They take the service via
   `RegisterRoutes(mux, svc, jwt)`. Authenticated identity is pulled
   via `auth.UserFromContext(r.Context())` -- do NOT parse
   Authorization headers manually.
2. Services take a Repository interface, NEVER `*gorm.DB`.
3. The adapter is the ONLY file in this resource that imports
   `gorm.io/gorm`. Other files use the abstract interface.
4. DTOs in `models.go` are SEPARATE from GORM entities. The GORM
   entities live in `internal/models/models.go` (a single shared
   package). Assume the entity for `{item_class}` already exists in
   `internal/models` -- do NOT add or modify entities there.
5. Domain errors flow as `fmt.Errorf("%w: detail", shared.ErrNotFound)`
   etc.; `routes.go` translates them with `errors.Is(err, shared.ErrXxx)`.
6. `depts.go` is the only place that wires adapter -> service.

Available shared helpers from `github.com/example/go-ddd-skel/internal/shared`:
- Sentinel errors: `shared.ErrNotFound`, `shared.ErrConflict`,
  `shared.ErrValidation`, `shared.ErrUnauthorized`, `shared.ErrForbidden`.
- `shared.WriteJSON(w http.ResponseWriter, status int, body any)` --
  JSON success helper.
- `shared.WriteError(w http.ResponseWriter, status int, detail string)`
  -- writes the wrapper-shared `{{detail, status}}` envelope.
- `shared.DecodeJSON(r *http.Request, dst any) error` -- decodes the
  request body with unknown-field rejection.
- `shared.PathID(r *http.Request, name string) (uint, error)` --
  parses `r.PathValue(name)` into uint.
- `shared.IsUniqueViolation(err error) bool` -- driver-agnostic
  unique-constraint detector (use it inside adapters).

Auth (JWT):
- Middleware is provided by
  `auth.Middleware(cfg config.Config, repo users.Repository) func(http.Handler) http.Handler`.
  `main.go` builds it once as `jwt := auth.Middleware(cfg, userRepo)`
  and passes it into every resource's `RegisterRoutes(mux, svc, jwt)`.
- The new module's `RegisterRoutes` MUST accept the same
  `jwt func(http.Handler) http.Handler` parameter and wrap every
  protected route with it: `mux.Handle("GET /api/{items_plural}", jwt(http.HandlerFunc(r.handleListXxx)))`.
- Inside a handler, `user, _ := auth.UserFromContext(r.Context())`
  returns `auth.User{{ID, Username}}`. Import path:
  `github.com/example/go-ddd-skel/internal/auth`.

GORM conventions (adapters/sql.go only):
- Use `r.db.WithContext(ctx).Find(&rows)`, `.First(&entity, id)`,
  `.Save(entity)`, `.Delete(&Entity{{}}, id)`.
- Wrap `gorm.ErrRecordNotFound` with
  `fmt.Errorf("%w: {item_name} %d", shared.ErrNotFound, id)`.
- Wrap unique-constraint failures via
  `if shared.IsUniqueViolation(err) {{ return fmt.Errorf("%w: %s", shared.ErrConflict, err.Error()) }}`.
- `created_at` / `updated_at` columns are managed by struct tags
  (`autoCreateTime` / `autoUpdateTime`) on the entity in
  `internal/models/models.go` -- do NOT set them manually.

JSON shape (wrapper-shared contract):
- All keys are `snake_case` via `json:"..."` struct tags.
- Foreign keys land as `category_id` not `category`.
- Datetimes use Go's default `time.Time.MarshalJSON` (ISO 8601).
- Optional / nullable FKs use pointer types: `*uint`, `*string`.

Shared environment (every backend in the wrapper relies on the same
env vars from `<wrapper>/.env`):
- `DATABASE_URL` -- common database (resolved by
  `internal/config/config.FromEnv()`).
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`.
NEVER call `os.Getenv` from a resource module -- use the `cfg`
threaded through `main.go` -> `auth.Middleware`.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match indentation (tabs), brace style, and import grouping of the
  reference resource (`internal/items/`) exactly.
- Group imports as: stdlib block, blank line, third-party block
  (e.g. `gorm.io/gorm`), blank line, internal block
  (`github.com/example/go-ddd-skel/...`).
- When `{auth_type}` is `none`, drop the `jwt` middleware wrap from
  routes (still accept the parameter) and drop owner-isolation
  checks if any. The route paths stay the same.
- Do NOT introduce new dependencies.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""


MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `go build ./...` and `go vet ./...` after generation to "
        "confirm the new internal/{item_name}/ module compiles. The "
        "wrapper-shared <wrapper>/.env is wired in via "
        "internal/config/config.go; main.go is the only file outside "
        "internal/{item_name}/ that this manifest edits. The entity "
        "type in internal/models/models.go is assumed to already exist."
    ),
    "targets": [
        {
            "path": "internal/{item_name}/models.go",
            "template": "internal/items/models.go",
            "language": "go",
            "description": (
                "internal/{item_name}/models.go -- DTOs + Repository "
                "marker types for `{item_class}`"
            ),
            "prompt": """\
Create `internal/{item_name}/models.go` for the `{item_class}` resource.

This file declares the DTO shapes the service layer accepts and a
type alias re-exporting the GORM entity from `internal/models`. It
does NOT declare GORM tags itself -- those live on the entity in
`internal/models/models.go` (assumed to already exist).

Required contents:
- `package {item_name}` declaration with a short doc comment
  explaining the resource's HTTP surface (mirrors the reference).
- Import `context` and
  `github.com/example/go-ddd-skel/internal/models`.
- A type alias re-exporting the entity:
  `type {item_class} = models.{item_class}`.
- Input DTOs (plain structs, no json tags -- those live on the
  HTTP-layer payload struct in `routes.go`):
  - `New{item_class}` -- fields the user can supply at create time.
  - `{item_class}Update` -- fields the user can supply at update
    time (use pointer types for partial updates).
  - `{item_class}Dto` -- response shape if you need a projection
    distinct from the entity (otherwise alias the entity and skip
    this struct).
- The Repository interface for this resource (kept here so callers
  importing `{item_name}` get the abstraction in one symbol):
  ```go
  type {item_class}Repository interface {{
      List(ctx context.Context) ([]{item_class}, error)
      Get(ctx context.Context, id uint) ({item_class}, error)
      Save(ctx context.Context, entity *{item_class}) error
      Update(ctx context.Context, entity *{item_class}) error
      Delete(ctx context.Context, id uint) error
  }}
  ```

REFERENCE (`internal/items/models.go` -- adapt the structure for
`{item_class}`; the reference declares both the type alias and the
input DTO):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "internal/{item_name}/repository.go",
            "template": "internal/items/models.go",
            "language": "go",
            "description": (
                "internal/{item_name}/repository.go -- abstract "
                "Repository interface (alternate location to models.go)"
            ),
            "prompt": """\
Create `internal/{item_name}/repository.go`. This file declares ONLY
the abstract `{item_class}Repository` interface that
`adapters/sql.go` will implement and that `service.go` will depend
on.

If you already declared `{item_class}Repository` inside
`models.go` (the reference puts the interface there), keep this file
minimal: a `package {item_name}` declaration plus a one-line doc
comment pointing readers at `models.go` for the interface
definition. Do NOT redeclare the interface -- Go will refuse to
compile two declarations of the same name.

Reference for the interface signature you must NOT redeclare:
```go
type {item_class}Repository interface {{
    List(ctx context.Context) ([]{item_class}, error)
    Get(ctx context.Context, id uint) ({item_class}, error)
    Save(ctx context.Context, entity *{item_class}) error
    Update(ctx context.Context, entity *{item_class}) error
    Delete(ctx context.Context, id uint) error
}}
```

REFERENCE (`internal/items/models.go` -- shows where the
canonical resource keeps its Repository interface):
---
{template}
---

Output only the file's contents (typically just the package
declaration plus a doc comment).
""",
        },
        {
            "path": "internal/{item_name}/adapters/sql.go",
            "template": "internal/items/adapters/sql.go",
            "language": "go",
            "description": (
                "internal/{item_name}/adapters/sql.go -- GORM "
                "implementation of {item_class}Repository"
            ),
            "prompt": """\
Create `internal/{item_name}/adapters/sql.go`. This is the ONLY file
in the `{item_name}` resource that imports `gorm.io/gorm`.

Required contents:
- `package adapters` declaration with a doc comment matching the
  reference's tone (it explains why adapters live in a sub-package
  to avoid the import cycle between `depts.go` and the parent
  resource package).
- Imports: `context`, `errors`, `fmt`, `gorm.io/gorm`,
  `github.com/example/go-ddd-skel/internal/models`,
  `github.com/example/go-ddd-skel/internal/shared`.
- `type Gorm{item_class}Repository struct {{ db *gorm.DB }}`.
- `func NewGorm{item_class}Repository(db *gorm.DB) *Gorm{item_class}Repository`
  -- returns the concrete pointer so `depts.go` can wrap it in the
  resource's interface.
- Methods implementing every Repository method using
  `r.db.WithContext(ctx)`:
  - `List` -- `Find(&rows)` ordered by `created_at DESC, id DESC`.
  - `Get` -- `First(&entity, id)`; wrap `gorm.ErrRecordNotFound` as
    `fmt.Errorf("%w: {item_name} %d", shared.ErrNotFound, id)`.
  - `Save` / `Update` -- `Save(entity)`; wrap unique violations via
    `shared.IsUniqueViolation` -> `shared.ErrConflict`.
  - `Delete` -- `Delete(&models.{item_class}{{}}, id)`; when
    `RowsAffected == 0`, wrap as `shared.ErrNotFound`.

Use `models.{item_class}` (NOT `{item_name}.{item_class}`) for entity
references -- importing the parent resource package would create a
cycle since the resource's `depts.go` imports this adapter.

REFERENCE (`internal/items/adapters/sql.go` -- adapt every line for
`{item_class}`, preserving structure, error wrapping, and import
ordering):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "internal/{item_name}/service.go",
            "template": "internal/items/service.go",
            "language": "go",
            "description": (
                "internal/{item_name}/service.go -- business logic over "
                "{item_class}Repository"
            ),
            "prompt": """\
Create `internal/{item_name}/service.go`. This is the resource's
business-logic layer.

Required contents:
- `package {item_name}` declaration with a doc comment matching the
  reference's tone.
- Imports: `context`, `fmt`, `strings`,
  `github.com/example/go-ddd-skel/internal/shared`.
- `type Service struct {{ repo {item_class}Repository }}`.
- `func NewService(repo {item_class}Repository) *Service` -- the
  service depends on the abstract interface, NEVER on `*gorm.DB`.
- Methods:
  - `List(ctx context.Context) ([]{item_class}, error)`
  - `Get(ctx context.Context, id uint) ({item_class}, error)`
  - `Create(ctx context.Context, dto New{item_class}) ({item_class}, error)`
    -- validate non-empty required fields and return
    `fmt.Errorf("%w: ...", shared.ErrValidation)` on bad input.
  - `Update(ctx context.Context, id uint, patch {item_class}Update) ({item_class}, error)`
    -- fetch via `repo.Get`, apply non-nil patch fields, persist via
    `repo.Update`.
  - `Delete(ctx context.Context, id uint) error`.

The service translates DTOs into entity values, calls the
repository, and returns domain errors wrapped with
`fmt.Errorf("%w: ...", shared.ErrXxx)`. Routes are responsible for
turning those errors into HTTP statuses via `errors.Is`.

REFERENCE (`internal/items/service.go`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "internal/{item_name}/depts.go",
            "template": "internal/items/depts.go",
            "language": "go",
            "description": (
                "internal/{item_name}/depts.go -- composition root "
                "wiring adapter -> service"
            ),
            "prompt": """\
Create `internal/{item_name}/depts.go`. This is the ONLY place in
the resource that wires the adapter into the service.

Required contents:
- `package {item_name}` declaration with a short doc comment.
- Imports: `gorm.io/gorm` and
  `github.com/example/go-ddd-skel/internal/{item_name}/adapters`.
- `func NewServiceFromDB(db *gorm.DB) *Service` -- builds a
  `*Gorm{item_class}Repository` via the adapter package and hands it
  to `NewService`.

Match the reference verbatim except for the entity / type names.

REFERENCE (`internal/items/depts.go`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "internal/{item_name}/routes.go",
            "template": "internal/items/routes.go",
            "language": "go",
            "description": (
                "internal/{item_name}/routes.go -- HTTP layer mounting "
                "/api/{items_plural}"
            ),
            "prompt": """\
Create `internal/{item_name}/routes.go`. This is the HTTP layer for
the `{item_class}` resource. It NEVER imports `gorm.io/gorm`.

Required contents:
- `package {item_name}` declaration with a doc comment matching the
  reference's tone.
- Imports: `errors`, `net/http`,
  `github.com/example/go-ddd-skel/internal/auth`,
  `github.com/example/go-ddd-skel/internal/shared`.
- `type Routes struct {{ svc *Service }}` and
  `func NewRoutes(svc *Service) *Routes`.
- `func RegisterRoutes(mux *http.ServeMux, svc *Service, jwt func(http.Handler) http.Handler)`
  mounting these endpoints (every route wrapped with `jwt(...)` when
  `{auth_type}` is not `none`):
  - `GET    /api/{items_plural}`         -> `handleList`
  - `POST   /api/{items_plural}`         -> `handleCreate`
  - `GET    /api/{items_plural}/{{id}}`  -> `handleGet`
  - `PATCH  /api/{items_plural}/{{id}}`  -> `handleUpdate`
  - `DELETE /api/{items_plural}/{{id}}`  -> `handleDelete`
- A small private payload struct for incoming bodies with
  `json:"snake_case"` tags (mirror the reference's `itemPayload`).
- Handler methods on `*Routes` that:
  - Parse via `shared.DecodeJSON` and `shared.PathID`.
  - Call exactly ONE service method.
  - Translate errors via a private helper
    `write{item_class}Error(w http.ResponseWriter, err error, fallback string)`
    that uses `errors.Is(err, shared.ErrNotFound|ErrValidation|ErrConflict)`
    to pick the HTTP status and falls through to 500 otherwise.
  - Use `shared.WriteJSON(w, http.StatusXxx, body)` for success.
- When the handler needs the authenticated principal:
  `user, _ := auth.UserFromContext(r.Context())`. `auth.User` exposes
  `ID int64` and `Username string`. (When `{auth_type}` is `none`,
  drop the `auth.UserFromContext` call and remove the `auth` import.)

REFERENCE (`internal/items/routes.go` -- preserve the
`writeItemError` -> `write{item_class}Error` rename pattern, the
payload-struct shape, and the handler structure):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "main.go",
            "template": "main.go",
            "language": "go",
            "description": (
                "main.go -- wire {item_class} resource into the "
                "composition root"
            ),
            "prompt": """\
Rewrite `main.go` to wire the new `{item_class}` resource into the
composition root.

CRITICAL CONSTRAINTS:
- Reproduce the EXISTING `main.go` content verbatim except for the
  two additions described below. Do NOT remove any existing
  imports, services, or `RegisterRoutes` calls.
- Preserve the import ordering (stdlib block, blank line, internal
  `github.com/example/go-ddd-skel/...` block).

Two minimal additions:

1. Add an import line in the internal block (alphabetised among the
   existing `github.com/example/go-ddd-skel/internal/<resource>`
   entries):

       "github.com/example/go-ddd-skel/internal/{item_name}"

2. After the existing service constructions (e.g.
   `orderSvc := orders.NewServiceFromDB(conn)`), add ONE line:

       {item_name}Svc := {item_name}.NewServiceFromDB(conn)

   And after the existing `RegisterRoutes` calls (e.g.
   `orders.RegisterRoutes(mux, orderSvc, jwt)`), add ONE line:

       {item_name}.RegisterRoutes(mux, {item_name}Svc, jwt)

The log line, graceful-shutdown plumbing, and `handleIndex` /
`handleHealth` helpers all stay unchanged.

REFERENCE (`main.go` -- current content; reproduce with only the
two additions above):
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
# ``go-skel.py``'s integration manifest but with paths and prompt text
# updated for the DDD layout (no ``handlers.Deps`` -- we describe the
# per-resource module convention instead).


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Go engineer integrating a freshly generated Go
service into an existing dev_skel multi-service wrapper. The service
uses the DDD per-resource layout: each CRUD resource lives under
`internal/<resource>/` with the five-file split (models / repository
/ adapters/sql / service / depts / routes).

The new service is `{service_label}` (slug `{service_slug}`, tech
`go-ddd-skel`). It already ships:
- The wrapper-shared `Item` resource at `internal/items/` mounted at
  `/api/items` (see the reference resource module for the canonical
  layout).
- Wrapper-shared `Category`, `Order`, `Catalog`, and `State`
  resources, each in its own `internal/<resource>/` module.
- A user-chosen `{item_class}` module under `internal/{item_name}/`
  mounted at `/api/{items_plural}` (the per-target manifest added it).
- JWT auth via `auth.Middleware(cfg, userRepo)` from
  `internal/auth`. The middleware loads users via
  `users.Repository` -- it never touches `*gorm.DB` directly. The JWT
  secret comes from `config.Config` (the wrapper-shared secret --
  NEVER re-read from `os.Getenv` in resource code).
- `internal/shared` exports the sentinel domain errors
  (`ErrNotFound`, `ErrConflict`, `ErrValidation`, `ErrUnauthorized`,
  `ErrForbidden`) plus `WriteJSON` / `WriteError` / `DecodeJSON` /
  `PathID` / `IsUniqueViolation` HTTP helpers.
- Module path is `github.com/example/go-ddd-skel`. The wrapper-shared
  `<wrapper>/.env` is loaded by `internal/config/config.go`
  (`Config.FromEnv()` + `loadDotenv()`) so `DATABASE_URL` and the JWT
  vars are identical to every other backend in the project.
- DB driver is GORM with the pure-Go SQLite dialect. No `database/sql`
  raw queries in resource code.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Go client package (under `internal/integrations/`) for
   each sibling backend the new service should call. Each client must
   read the sibling's URL from
   `os.Getenv("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Integration tests (`integration_test.go` in `package main`) that
   exercise the cross-service flows end-to-end via the wrapper-shared
   SQLite database (and, when sibling backends are present, via the
   typed clients above).

Coding rules:
- Use `net/http` for sibling HTTP calls. Do NOT add new dependencies.
- Read JWT material via `config.FromEnv()`. NEVER hardcode the
  secret. NEVER call `os.Getenv("JWT_SECRET")` in resource code.
- Use `encoding/json` for request/response structs.
- Use the standard `testing` package. Guard sibling calls with a
  helper that checks the env var and calls `t.Skip()` when the var
  is missing or the sibling is unreachable.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items` and `/api/{items_plural}`
  endpoints. Do not assume sibling services exist; gracefully degrade.

User-supplied integration instructions (free-form, take with the
same weight as the rules above):
{integration_extra}

User-supplied backend instructions (already applied during the
per-target phase, repeated here so the integration code stays
consistent):
{backend_extra}
"""


INTEGRATION_MANIFEST = {
    "system_prompt": INTEGRATION_SYSTEM_PROMPT,
    "notes": (
        "Integration phase: writes internal/integrations/clients.go "
        "and integration_test.go, then runs the test-and-fix loop "
        "via `go test ./... 2>&1 || ./test`."
    ),
    "test_command": "go test ./... 2>&1 || ./test",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "internal/integrations/clients.go",
            "language": "go",
            "description": (
                "internal/integrations/clients.go -- typed HTTP clients "
                "for sibling backends"
            ),
            "prompt": """\
Create `internal/integrations/clients.go`. The package exposes one
typed client struct per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:
- Package name: `integrations`.
- Use `net/http` and `encoding/json` for HTTP calls (keeps the
  dependency list unchanged). Do NOT add external HTTP client libs.
- Each sibling backend gets a struct named `<PascalSlug>Client`
  with a `New<PascalSlug>Client(token string) (*<PascalSlug>Client, error)`
  constructor that:
    - Reads its base URL from
      `os.Getenv("SERVICE_URL_<UPPER_SLUG>")`.
    - Returns `(nil, IntegrationError)` when the env var is missing.
    - Stores the optional bearer `token`; when non-empty, every
      request sends `Authorization: Bearer <token>`.
- Methods every sibling exposes:
    - `ListItems() ([]map[string]any, error)` -> hits the sibling's
      `/api/items`.
    - `GetState(key string) (map[string]any, error)` -> hits the
      sibling's `/api/state/<key>`.
- Define a custom `IntegrationError` type implementing `error` at
  the top of the file (status code + body).
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define `IntegrationError` and a comment
  `// No sibling clients -- {sibling_count} siblings discovered.`
  Do NOT define dummy client structs for non-existent siblings.

Output the full file contents only.
""",
        },
        {
            "path": "integration_test.go",
            "language": "go",
            "description": (
                "integration_test.go -- cross-service integration tests "
                "in package main"
            ),
            "prompt": """\
Write `integration_test.go` in `package main`. Integration tests
that exercise the new `{service_label}` service end-to-end and (when
sibling backends are present) verify the cross-service flow.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use the standard `testing` package. Test functions are
  `func TestXxx(t *testing.T)`.
- Guard sibling client calls: check the env var with `os.Getenv` and
  call `t.Skip("SERVICE_URL_<SLUG> not set")` when missing or the
  sibling is unreachable.
- Use `net/http` for HTTP calls.
- Resource modules are addressable as
  `github.com/example/go-ddd-skel/internal/<resource>` -- the new
  resource is `internal/{item_name}` and exposes `NewServiceFromDB`
  via its `depts.go`.

Required tests:
1. `TestItemsEndpointRoundTrip` -- via the `items.Service` wired up
   from a temp SQLite DB, insert and read back an `Item`, asserting
   the row round-trips.
2. `TestReactStateRoundTrip` -- create a `state` row with
   key="test_key" and a JSON-encoded value, read it back, assert the
   value matches.
3. `Test{item_class}EndpointUsesJWT` -- verify
   `os.Getenv("JWT_SECRET")` is non-empty (the service reads it via
   `config.FromEnv()`).
4. `TestJWTSecretIsWrapperShared` -- assert
   `os.Getenv("JWT_SECRET")` is non-empty.
5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `TestSibling<PascalSlug>ItemsVisibleViaSharedDB`. Guard
   with:
   ```go
   url := os.Getenv("SERVICE_URL_<UPPER_SLUG>")
   if url == "" {{
       t.Skip("SERVICE_URL_<SLUG> not set")
   }}
   ```
   Then call the sibling's `/api/items` and skip if unreachable.
6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Use tabs for indentation (standard Go). Output the full file
contents only.
""",
        },
    ],
}
