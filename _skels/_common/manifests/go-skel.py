"""AI manifest for the ``go-skel`` skeleton.

The skeleton ships a pure-Go HTTP service built on ``net/http`` with
Go 1.22+ method-aware routing. Handlers live in
``internal/handlers/handlers.go`` as methods on a ``Deps`` struct
(fields ``Cfg config.Config``, ``DB *sql.DB``). Routes are registered
by ``handlers.Register(mux, deps)`` called from ``main.go``.

Auth uses ``auth.Middleware(cfg, db)`` which returns a
``func(http.Handler) http.Handler`` — wrapping a handler enforces JWT.
Authenticated identity is retrieved via ``auth.UserFromContext(ctx)``.

DB access is raw ``database/sql`` with ``modernc.org/sqlite`` as the
driver. There is no ORM or ``sqlx`` — use ``db.QueryContext``,
``db.ExecContext``, ``db.QueryRowContext``.

This manifest tells ``_bin/skel-gen-ai`` how to add a ``{item_class}``
CRUD handler file in a SEPARATE file
``internal/handlers/{item_name}.go`` (same ``package handlers``) and
wire it into ``main.go`` via the existing ``Register`` function.
"""

SYSTEM_PROMPT = """\
You are a senior Go engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton.

Project layout (CRITICAL -- read carefully):
- The Go module root is `{service_subdir}/`. Source lives under the
  module root plus `internal/` for private packages.
- The entry point is `main.go`.
- All HTTP handlers live in `internal/handlers/` as methods on the
  `Deps` struct:
    type Deps struct {{
        Cfg config.Config
        DB  *sql.DB
    }}
  Routes are registered in the `Register(mux *http.ServeMux, d Deps)`
  function called from `main.go`.
- The module already depends on: `net/http` (Go 1.22 method-aware
  ServeMux), `database/sql`, `encoding/json`, `modernc.org/sqlite`
  (pure-Go SQLite driver), `github.com/golang-jwt/jwt/v5`,
  `golang.org/x/crypto/bcrypt`, `github.com/joho/godotenv`.
  Do NOT add new dependencies.
- There is **NO** ORM or `sqlx`. Use `database/sql` directly:
  `d.DB.QueryContext`, `d.DB.ExecContext`, `d.DB.QueryRowContext`.
- Struct fields (payload/response) use JSON tags for serialisation:
  `json:"field_name"`. Nullable fields use pointer types
  (`*string`, `*int64`).
- Authentication is provided by `auth.Middleware(d.Cfg, d.DB)` from
  `internal/auth`. It returns `func(http.Handler) http.Handler`.
  Wrap a handler with `jwt(http.HandlerFunc(d.handleFoo))` where
  `jwt := auth.Middleware(d.Cfg, d.DB)`. Inside the handler, use
  `user, _ := auth.UserFromContext(r.Context())` to get the
  authenticated user. Do NOT manually parse Authorization headers.
- Error responses use the `writeError(w, status, detail)` and
  `writeJSON(w, status, body)` helper functions already defined in
  `handlers.go`. Do NOT redefine them — they are package-level
  and visible from any file in `package handlers`.
- Path parameters use Go 1.22's `r.PathValue("id")`. The existing
  `pathID(r)` helper parses `r.PathValue("id")` into `int64` — it
  is also package-level and visible.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The DB table for the new entity MUST be
  named `{items_plural}`.

Shared environment (CRITICAL -- every backend in the wrapper relies on
the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` -- common database.
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`.
  These are read by `config.FromEnv()` in `internal/config/config.go`.
  NEVER call `os.Getenv` in handler code -- use `d.Cfg.*`.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match the indentation, brace style, and import grouping of the
  existing `internal/handlers/handlers.go` exactly.
- All handler files share `package handlers` -- do NOT use a
  different package name.
- Use `encoding/json` for serialisation, `database/sql` for DB
  access, `net/http` for request/response types.
- Do NOT redefine `writeJSON`, `writeError`, `decodeJSON`, or
  `pathID` -- they are already defined in `handlers.go` and visible
  package-wide.
- Do NOT import `internal/auth` for the middleware setup -- that is
  done in `Register` (also in `handlers.go`). Only import it if you
  need `auth.UserFromContext` inside a handler.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `go build ./...` after generation to confirm the new "
        "{item_class} handlers compile. The wrapper-shared `<wrapper>/.env` "
        "is already wired in via `internal/config/config.go`."
    ),
    "targets": [
        {
            "path": "internal/handlers/{item_name}.go",
            "template": None,
            "language": "go",
            "description": (
                "internal/handlers/{item_name}.go -- CRUD handlers for "
                "`{item_class}`"
            ),
            "prompt": """\
IMPORTANT: You are creating a NEW file at
`internal/handlers/{item_name}.go` inside the SAME `package handlers`
as the existing `handlers.go`. All package-level helpers (`writeJSON`,
`writeError`, `decodeJSON`, `pathID`) and the `Deps` struct are
already defined in `handlers.go` and MUST NOT be redefined.

CRITICAL CONSTRAINTS -- violations cause compile failures:
- Do NOT redefine `Deps`, `writeJSON`, `writeError`, `decodeJSON`, or
  `pathID` -- they already exist in `handlers.go`.
- Do NOT use `sqlx`, `gorm`, or any ORM. Use `database/sql` directly
  via `d.DB.QueryContext`, `d.DB.ExecContext`, `d.DB.QueryRowContext`.
- Do NOT manually parse `Authorization` headers. Authentication is
  wired in `Register` via `auth.Middleware`; if you need the user
  identity inside a handler, call
  `user, _ := auth.UserFromContext(r.Context())`.
- Do NOT import `internal/config` -- the config is already in `d.Cfg`
  (type `config.Config`) via the `Deps` struct.

Create `internal/handlers/{item_name}.go` with CRUD handlers for the
`{item_class}` entity, to be mounted under `/api/{items_plural}`.

Here is a COMPILABLE REFERENCE showing the exact patterns you MUST
follow. This is adapted from the existing items/categories code in
`handlers.go` -- adapt it for `{item_class}`:

```go
package handlers

import (
	"database/sql"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/example/go-skel/internal/auth"
)

// {item_name}Row is the JSON-serialisable representation of a
// `{items_plural}` table row.
type {item_name}Row struct {{
	ID          int64   `json:"id"`
	Name        string  `json:"name"`
	Description *string `json:"description"`
	CreatedAt   string  `json:"created_at"`
	UpdatedAt   string  `json:"updated_at"`
}}

type create{item_class}Payload struct {{
	Name        string  `json:"name"`
	Description *string `json:"description"`
}}

func (d Deps) handleList{item_class}s(w http.ResponseWriter, r *http.Request) {{
	rows, err := d.DB.QueryContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM {items_plural} ORDER BY id`)
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "list {items_plural} failed: "+err.Error())
		return
	}}
	defer rows.Close()
	out := []{item_name}Row{{}}
	for rows.Next() {{
		var row {item_name}Row
		if err := rows.Scan(&row.ID, &row.Name, &row.Description, &row.CreatedAt, &row.UpdatedAt); err != nil {{
			writeError(w, http.StatusInternalServerError, "scan {item_name} failed: "+err.Error())
			return
		}}
		out = append(out, row)
	}}
	if err := rows.Err(); err != nil {{
		writeError(w, http.StatusInternalServerError, "rows.Err: "+err.Error())
		return
	}}
	writeJSON(w, http.StatusOK, out)
}}

func (d Deps) handleCreate{item_class}(w http.ResponseWriter, r *http.Request) {{
	var body create{item_class}Payload
	if err := decodeJSON(r, &body); err != nil {{
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}}
	if strings.TrimSpace(body.Name) == "" {{
		writeError(w, http.StatusBadRequest, "{item_name} name cannot be empty")
		return
	}}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`INSERT INTO {items_plural} (name, description, created_at, updated_at)
		 VALUES (?, ?, ?, ?)`,
		body.Name, body.Description, now, now,
	)
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "insert {item_name} failed: "+err.Error())
		return
	}}
	id, err := res.LastInsertId()
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "could not read new {item_name} id")
		return
	}}
	writeJSON(w, http.StatusCreated, {item_name}Row{{
		ID:          id,
		Name:        body.Name,
		Description: body.Description,
		CreatedAt:   now,
		UpdatedAt:   now,
	}})
}}

func (d Deps) handleGet{item_class}(w http.ResponseWriter, r *http.Request) {{
	id, err := pathID(r)
	if err != nil {{
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}}
	var row {item_name}Row
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM {items_plural} WHERE id = ?`, id,
	).Scan(&row.ID, &row.Name, &row.Description, &row.CreatedAt, &row.UpdatedAt)
	if err != nil {{
		if errors.Is(err, sql.ErrNoRows) {{
			writeError(w, http.StatusNotFound, "{item_name} not found")
			return
		}}
		writeError(w, http.StatusInternalServerError, "fetch {item_name} failed: "+err.Error())
		return
	}}
	writeJSON(w, http.StatusOK, row)
}}

func (d Deps) handleUpdate{item_class}(w http.ResponseWriter, r *http.Request) {{
	id, err := pathID(r)
	if err != nil {{
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}}
	var body create{item_class}Payload
	if err := decodeJSON(r, &body); err != nil {{
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}}
	if strings.TrimSpace(body.Name) == "" {{
		writeError(w, http.StatusBadRequest, "{item_name} name cannot be empty")
		return
	}}
	now := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	res, err := d.DB.ExecContext(r.Context(),
		`UPDATE {items_plural} SET name = ?, description = ?, updated_at = ?
		   WHERE id = ?`,
		body.Name, body.Description, now, id,
	)
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "update {item_name} failed: "+err.Error())
		return
	}}
	rows, _ := res.RowsAffected()
	if rows == 0 {{
		writeError(w, http.StatusNotFound, "{item_name} not found")
		return
	}}
	var updated {item_name}Row
	err = d.DB.QueryRowContext(r.Context(),
		`SELECT id, name, description, created_at, updated_at
		   FROM {items_plural} WHERE id = ?`, id,
	).Scan(&updated.ID, &updated.Name, &updated.Description, &updated.CreatedAt, &updated.UpdatedAt)
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "refetch {item_name} failed: "+err.Error())
		return
	}}
	writeJSON(w, http.StatusOK, updated)
}}

func (d Deps) handleDelete{item_class}(w http.ResponseWriter, r *http.Request) {{
	id, err := pathID(r)
	if err != nil {{
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}}
	res, err := d.DB.ExecContext(r.Context(),
		`DELETE FROM {items_plural} WHERE id = ?`, id,
	)
	if err != nil {{
		writeError(w, http.StatusInternalServerError, "delete {item_name} failed: "+err.Error())
		return
	}}
	rows, _ := res.RowsAffected()
	if rows == 0 {{
		writeError(w, http.StatusNotFound, "{item_name} not found")
		return
	}}
	w.WriteHeader(http.StatusNoContent)
}}
```

Adapt the above for `{item_class}`. You may add extra fields or
endpoints but the structure, imports, and patterns MUST match
exactly. When `{auth_type}` is `none`, remove the
`auth.UserFromContext` call and the `"github.com/example/go-skel/internal/auth"`
import. Note: the `auth` import is only needed if a handler calls
`auth.UserFromContext` -- the JWT middleware wiring happens in
`Register` (in `handlers.go`), not in the individual handler file.

Output only the file's contents.
""",
        },
        {
            "path": "main.go",
            "template": "main.go",
            "language": "go",
            "description": (
                "main.go -- rewrite to register {item_class} routes alongside "
                "existing handlers"
            ),
            "prompt": """\
Rewrite `main.go` to ensure the new `{item_class}` routes are
registered alongside the existing routes.

CRITICAL: The route registration happens INSIDE
`handlers.Register(mux, deps)` in `internal/handlers/handlers.go`,
NOT in `main.go`. `main.go` simply calls `handlers.Register(mux, deps)`.

What you MUST actually change is the `Register` function in
`internal/handlers/handlers.go` (but since this target path is
`main.go`, you are rewriting `main.go` itself). Since the new
handler file `internal/handlers/{item_name}.go` defines methods on
`Deps`, the `Register` function in `handlers.go` needs new route
lines -- but that file is not this target.

**For `main.go` itself**: the file should remain essentially
unchanged. The only necessary update is ensuring it still compiles
and correctly references the `handlers` package. Reproduce the
existing `main.go` content with only cosmetic changes if needed.

HOWEVER -- because the route wiring lives in `handlers.Register`,
you should ADD the new routes there. Since this target writes
`main.go`, include a comment at the top noting the new entity.

Here is the EXISTING `main.go` to reproduce (with the new {item_class}
entity noted in the log line):

REFERENCE (`main.go` -- current content):
---
{template}
---

Reproduce the reference content. The ONLY change you should make is
updating the log line to mention the new entity, e.g.:
  log.Printf("go-skel listening on %s (db=%s, issuer=%s, entities=[items,categories,{items_plural}])", ...)

Output only the file's contents.
""",
        },
        {
            "path": "internal/handlers/handlers.go",
            "template": "internal/handlers/handlers.go",
            "language": "go",
            "description": (
                "internal/handlers/handlers.go -- add {item_class} route "
                "registration to Register()"
            ),
            "prompt": """\
Rewrite `internal/handlers/handlers.go` to register the new
`{item_class}` CRUD routes alongside the existing `categories`,
`items`, and `state` routes.

CRITICAL: Do NOT change the function signatures, do NOT restructure
the existing code, do NOT redefine any existing handlers, do NOT
remove any existing routes. The ONLY changes are:

1. Add new route registrations inside `Register()` for the
   `{item_class}` entity, after the existing items routes and before
   the state routes.
2. The new handler methods (`handleList{item_class}s`,
   `handleCreate{item_class}`, `handleGet{item_class}`,
   `handleUpdate{item_class}`, `handleDelete{item_class}`) are
   defined in `internal/handlers/{item_name}.go` -- they are methods
   on `Deps` and visible package-wide. Just add the `mux.Handle` lines.

The new routes to add (JWT-protected via the existing `jwt` variable):

```go
	mux.Handle("GET /api/{items_plural}", jwt(http.HandlerFunc(d.handleList{item_class}s)))
	mux.Handle("POST /api/{items_plural}", jwt(http.HandlerFunc(d.handleCreate{item_class})))
	mux.Handle("GET /api/{items_plural}/{{id}}", jwt(http.HandlerFunc(d.handleGet{item_class})))
	mux.Handle("PUT /api/{items_plural}/{{id}}", jwt(http.HandlerFunc(d.handleUpdate{item_class})))
	mux.Handle("DELETE /api/{items_plural}/{{id}}", jwt(http.HandlerFunc(d.handleDelete{item_class})))
```

REFERENCE (`internal/handlers/handlers.go` -- current content):
---
{{template}}
---

Reproduce the ENTIRE file with the new route lines added inside
`Register()`. Do NOT remove or alter ANY existing code. Output only
the file's contents.
""",
        },
    ],
}


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Go engineer integrating a freshly generated Go
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`go-skel`). It already ships:
- The wrapper-shared `Item` model + handlers mounted at `/api/items`
  using `database/sql` + `encoding/json` against the shared
  `DATABASE_URL`.
- The wrapper-shared `ReactState` model + handlers mounted at
  `/api/state` and `/api/state/{{key}}`.
- A user-chosen `{item_class}` model + handlers mounted at
  `/api/{items_plural}` (the per-target manifest added these for this
  run). Model structs are defined INLINE in each handler file within
  `internal/handlers/` -- there is no separate models package.
- JWT auth via `auth.Middleware(cfg, db)` from `internal/auth` --
  returns `func(http.Handler) http.Handler`. The JWT secret comes
  from `config.Config` (the wrapper-shared secret -- NEVER re-read
  from `os.Getenv` in handler code).
- All handlers are methods on `handlers.Deps` (fields `Cfg
  config.Config`, `DB *sql.DB`), registered via
  `handlers.Register(mux, deps)` in `main.go`.
- The wrapper-shared `<wrapper>/.env` is loaded by
  `internal/config/config.go` (`Config.FromEnv()` + `loadDotenv()`)
  so `DATABASE_URL` and the JWT vars are identical to every other
  backend in the project.
- DB driver is `modernc.org/sqlite` (pure Go). No ORM, no `sqlx`.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Go client package for each sibling backend the new service
   should call. The client must read the sibling's URL from
   `os.Getenv("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Integration tests (`integration_test.go`) that exercise the
   cross-service flows end-to-end via the wrapper-shared SQLite database
   (and, when sibling backends are present, via the typed clients above).

Coding rules:
- Use `net/http` for sibling HTTP calls. Do NOT add new dependencies.
- Read JWT material via `config.FromEnv()`. NEVER hardcode the secret.
  NEVER call `os.Getenv("JWT_SECRET")` in handler code.
- Use `encoding/json` for request/response structs.
- Use standard `testing` package. Guard sibling calls with a helper
  that checks the env var and calls `t.Skip()` when the var is missing
  or the sibling is unreachable.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items` and `/api/{items_plural}`
  endpoints. Do not assume sibling services exist; gracefully degrade.

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
                "internal/integrations/clients.go -- typed HTTP clients for "
                "sibling backends"
            ),
            "prompt": """\
Create `internal/integrations/clients.go`. The package exposes one
typed client struct per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Package name: `integrations`
- Use `net/http` and `encoding/json` for HTTP calls (keeps the
  dependency list unchanged). Do NOT add external HTTP client libs.
- Each sibling backend gets a struct named `<PascalSlug>Client`.
  The struct:
    - Reads its base URL from
      `os.Getenv("SERVICE_URL_<UPPER_SLUG>")` in a `New<PascalSlug>Client(token string)`
      constructor. Returns `(nil, error)` when the env var is missing.
    - Stores an optional `token string`; when non-empty, every
      request sends `Authorization: Bearer <token>`.
    - Exposes `ListItems() ([]map[string]any, error)` and
      `GetState(key string) (map[string]any, error)` methods that hit
      the sibling's wrapper-shared `/api/items` and
      `/api/state/<key>` endpoints.
- Define a custom `IntegrationError` type implementing `error`.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationError` type and add a comment
  `// No sibling clients -- {sibling_count} siblings discovered.`
  Do NOT define dummy client structs for non-existent siblings.

Output the full file contents only.
""",
        },
        {
            "path": "integration_test.go",
            "language": "go",
            "description": (
                "integration_test.go -- cross-service integration tests"
            ),
            "prompt": """\
Write `integration_test.go` in `package main`. Integration tests that
exercise the new `{service_label}` service end-to-end and (when
sibling backends are present) verify the cross-service flow.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use the standard `testing` package. Test functions are `func
  TestXxx(t *testing.T)`.
- Guard sibling client calls: check the env var with `os.Getenv` and
  call `t.Skip("SERVICE_URL_<SLUG> not set")` when missing or the
  sibling is unreachable.
- Use `net/http` for HTTP calls and `os/exec` for `sqlite3` CLI
  access if needed.

Required tests:

1. `TestItemsEndpointRoundTrip` -- insert an `Item` row into the
   `items` table via `sqlite3` CLI or direct DB access, then query
   via the service's `/api/items` endpoint (or directly via sqlite3)
   and assert the row exists.

2. `TestReactStateRoundTrip` -- insert a `ReactState` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `Test{item_class}EndpointUsesJWT` -- verify that
   `os.Getenv("JWT_SECRET")` is non-empty (the service reads it via
   `config.FromEnv()`).

4. `TestJWTSecretIsWrapperShared` -- assert that
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

Use tabs for indentation (standard Go). Output the full file contents
only.
""",
        },
    ],
}
