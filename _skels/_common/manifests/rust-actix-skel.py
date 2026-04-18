"""AI manifest for the ``rust-actix-skel`` skeleton.

The skeleton ships an Actix-web service with ``auth``, ``categories``,
``items``, and ``state`` handler modules, plus the wrapper-shared
``Config`` (in ``src/config.rs``) registered as ``web::Data<Config>``
and a ``SqlitePool`` registered as ``web::Data<SqlitePool>``.  This
manifest tells ``_bin/skel-gen-ai`` how to add a ``{item_class}`` CRUD
handler file — with **inline** request/response structs (NO separate
``models`` module) — and wire it into ``src/handlers/mod.rs``, exactly
matching the patterns already used by ``items.rs``.
"""

SYSTEM_PROMPT = """\
You are a senior Rust engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton.

Project layout (CRITICAL — read carefully):
- The Cargo crate root is `{service_subdir}/`. Source lives under
  `src/`. The existing entry point is `src/main.rs`.
- The crate already depends on `actix-web`, `serde`, `serde_json`,
  `chrono`, `sqlx` (sqlite), `tracing`, `tracing-actix-web`, `tokio`,
  `dotenvy`, `jsonwebtoken`, `argon2`, `thiserror`, and
  `futures-util`. Do NOT add new dependencies.
- There is **NO** `AppState` struct. Instead, the app registers shared
  resources directly as `web::Data`:
  - `web::Data<Config>` — the wrapper-shared `Config` from
    `src/config.rs`.
  - `web::Data<SqlitePool>` — the connection pool from `src/db.rs`.
  Handlers extract these via `pool: web::Data<SqlitePool>` (NOT
  `web::Data<Arc<AppState>>`).
- There is **NO** top-level `src/models.rs` module. Model / payload
  structs are defined **inline** in each handler file. For example,
  `src/handlers/items.rs` defines `ItemRow` and `CreateItemPayload`
  directly in the file. The new handler MUST follow the same pattern.
- Authentication is provided by the `AuthUser` extractor from
  `crate::auth`. Adding `_user: AuthUser` to a handler's parameter
  list automatically enforces JWT auth — the extractor reads the
  `Authorization: Bearer <token>` header, verifies the JWT via
  `crate::auth::verify_token`, and returns `ApiError::Unauthorized`
  (401) if invalid. Do NOT manually parse auth headers.
- Error handling uses `crate::error::ApiError` (derives `thiserror`).
  Handlers return `Result<HttpResponse, ApiError>`. Variants:
  `Validation(String)`, `Unauthorized(String)`, `NotFound(String)`,
  `Conflict(String)`, `Database(sqlx::Error)`, `Internal(String)`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The DB table for the new entity MUST be
  named `{items_plural}`.

Shared environment (CRITICAL — every backend in the wrapper relies on
the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` — common database.
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`.
  These are read by `Config::from_env()` in `src/config.rs`. NEVER
  re-read them from `std::env::var` in handler code.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match the indentation, brace style, and import order of the existing
  `src/handlers/items.rs` exactly.
- Use `serde::{{Deserialize, Serialize}}` for structs.
- Use `actix_web::{{get, post, web, HttpResponse}}` for handlers.
- Use `sqlx::query_as` / `sqlx::query` for database access with the
  `SqlitePool` from `web::Data<SqlitePool>`.
- Async functions returning `Result<HttpResponse, ApiError>`.
- Do NOT import `crate::models` — this module does not exist.
- Do NOT create a `src/models.rs` file.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `cargo check` after generation to confirm the new "
        "{item_class} module compiles. The wrapper-shared `<wrapper>/.env` "
        "is already wired in via `src/config.rs`."
    ),
    "targets": [
        {
            "path": "src/handlers/{item_name}.rs",
            "template": None,
            "language": "rust",
            "description": "src/handlers/{item_name}.rs — Actix handlers for `{item_class}`",
            "prompt": """\
IMPORTANT: The handlers directory is a MODULE DIRECTORY with
`src/handlers/mod.rs` (NOT a single `src/handlers.rs` file). You are
creating a NEW sub-module at `src/handlers/{item_name}.rs`. Do NOT
create `src/handlers.rs` — that would conflict with the existing
`src/handlers/mod.rs`.

CRITICAL CONSTRAINTS — violations cause `cargo check` failures:
- Do NOT import `crate::models` — this module does NOT exist in the
  skeleton. Define all structs INLINE in this file.
- Do NOT use `web::Data<Arc<AppState>>` — there is no `AppState`
  struct. Use `web::Data<SqlitePool>` for database access.
- Do NOT manually parse `Authorization` headers or use
  `actix_web::http::header::Header` on `Option<String>`. The skeleton
  uses the `AuthUser` extractor from `crate::auth` — just add
  `_user: AuthUser` as a handler parameter and auth is enforced
  automatically.
- Do NOT use `Responder` as a return type — use
  `Result<HttpResponse, ApiError>` for consistency with the existing
  handlers.

Create `src/handlers/{item_name}.rs` with Actix-web CRUD handlers for
the `{item_class}` entity, mounted under `/api/{items_plural}`.

Here is a COMPILABLE REFERENCE showing the exact patterns you MUST
follow. This is from the existing `src/handlers/items.rs` — adapt it
for `{item_class}`:

```rust
//! CRUD handlers for the `{items_plural}` table.

use actix_web::{{get, post, web, HttpResponse}};
use chrono::Utc;
use serde::{{Deserialize, Serialize}};
use sqlx::sqlite::SqlitePool;

use crate::auth::AuthUser;
use crate::error::ApiError;

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct {item_class}Row {{
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub is_completed: bool,
    pub created_at: String,
    pub updated_at: String,
}}

#[derive(Debug, Deserialize)]
pub struct Create{item_class}Payload {{
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub is_completed: bool,
}}

#[get("")]
pub async fn list_{items_plural}(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
) -> Result<HttpResponse, ApiError> {{
    let rows = sqlx::query_as::<_, {item_class}Row>(
        "SELECT id, name, description, is_completed, created_at, updated_at \\
         FROM {items_plural} ORDER BY created_at DESC, id DESC",
    )
    .fetch_all(pool.get_ref())
    .await?;
    Ok(HttpResponse::Ok().json(rows))
}}

#[post("")]
pub async fn create_{item_name}(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    payload: web::Json<Create{item_class}Payload>,
) -> Result<HttpResponse, ApiError> {{
    let p = payload.into_inner();
    if p.name.trim().is_empty() {{
        return Err(ApiError::Validation("{item_name} name cannot be empty".to_string()));
    }}
    let now = Utc::now().format("%Y-%m-%dT%H:%M:%.3fZ").to_string();
    let row: (i64,) = sqlx::query_as(
        "INSERT INTO {items_plural} (name, description, is_completed, created_at, updated_at) \\
         VALUES (?, ?, ?, ?, ?) RETURNING id",
    )
    .bind(&p.name)
    .bind(&p.description)
    .bind(p.is_completed)
    .bind(&now)
    .bind(&now)
    .fetch_one(pool.get_ref())
    .await?;
    let item = {item_class}Row {{
        id: row.0,
        name: p.name,
        description: p.description,
        is_completed: p.is_completed,
        created_at: now.clone(),
        updated_at: now,
    }};
    Ok(HttpResponse::Created().json(item))
}}

#[get("/{{id}}")]
pub async fn get_{item_name}(
    pool: web::Data<SqlitePool>,
    _user: AuthUser,
    path: web::Path<i64>,
) -> Result<HttpResponse, ApiError> {{
    let id = path.into_inner();
    let row = sqlx::query_as::<_, {item_class}Row>(
        "SELECT id, name, description, is_completed, created_at, updated_at \\
         FROM {items_plural} WHERE id = ?",
    )
    .bind(id)
    .fetch_optional(pool.get_ref())
    .await?;
    let item = row.ok_or_else(|| ApiError::NotFound(format!("{item_name} {{id}} not found")));
    Ok(HttpResponse::Ok().json(item?))
}}
```

Adapt the above for `{item_class}`. You may add extra fields or
endpoints but the structure, imports, derive macros, and patterns
MUST match exactly. When `{auth_type}` is `none`, remove the
`_user: AuthUser` parameter and the `use crate::auth::AuthUser;`
import.

Output only the file's contents.
""",
        },
        {
            "path": "src/handlers/mod.rs",
            "template": "src/handlers/mod.rs",
            "language": "rust",
            "description": "src/handlers/mod.rs — add {item_name} sub-module + route wiring",
            "prompt": """\
Rewrite `src/handlers/mod.rs` to include the new `{item_name}` sub-module
alongside the existing `auth`, `categories`, `items`, `state` modules.

CRITICAL: Do NOT change the function signature, do NOT add new imports,
do NOT restructure the existing code. The ONLY changes are:
1. Add `pub mod {item_name};` after the existing module declarations.
2. Add a new `.service(web::scope("/{items_plural}") ...)` block inside
   the `register()` function, wiring the new handlers.

Here is the EXACT output you must produce (the REFERENCE with the new
module added). Copy it verbatim, only adjusting if the reference
template has changed:

```rust
//! HTTP handlers, grouped by resource.
//!
//! Routes are registered in `main.rs` via `App::configure(register)`
//! so the wiring lives in one place and the per-module functions can
//! stay focused on a single resource.

pub mod auth;
pub mod categories;
pub mod items;
pub mod {item_name};
pub mod state;

use actix_web::web;

/// Mount every wrapper-shared route under `/api/...`. Called from
/// `main.rs` so a single `App::configure(handlers::register)` line
/// wires the entire backend.
pub fn register(cfg: &mut web::ServiceConfig) {{
    cfg.service(
        web::scope("/api")
            .service(
                web::scope("/auth")
                    .service(auth::register_handler)
                    .service(auth::login_handler),
            )
            .service(
                web::scope("/categories")
                    .service(categories::list_categories)
                    .service(categories::create_category)
                    .service(categories::get_category)
                    .service(categories::update_category)
                    .service(categories::delete_category),
            )
            .service(
                web::scope("/items")
                    .service(items::list_items)
                    .service(items::create_item)
                    .service(items::get_item)
                    .service(items::complete_item),
            )
            .service(
                web::scope("/{items_plural}")
                    .service({item_name}::list_{items_plural})
                    .service({item_name}::create_{item_name})
                    .service({item_name}::get_{item_name}),
            )
            .service(
                web::scope("/state")
                    .service(state::list_state)
                    .service(state::upsert_state)
                    .service(state::delete_state),
            ),
    );
}}
```

REFERENCE (`src/handlers/mod.rs` — current content before your edit):
---
{{template}}
---

Output only the file's contents.
""",
        },
    ],
}


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Rust engineer integrating a freshly generated Actix-web
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`rust-actix-skel`). It already ships:
- The wrapper-shared `Item` model + handlers mounted at `/api/items`
  using sqlx + serde against the shared `DATABASE_URL`.
- The wrapper-shared `ReactState` model + handlers mounted at `/api/state`
  and `/api/state/{{key}}`.
- A user-chosen `{item_class}` model + handlers (the per-target manifest
  rewrote `Item` to `{item_class}` for this run).
- JWT auth via the `AuthUser` extractor from `crate::auth` — handlers
  add `_user: AuthUser` to their parameter list and the extractor
  handles everything. The JWT secret comes from `web::Data<Config>`
  (the wrapper-shared secret — NEVER re-read from `std::env::var`).
- There is NO `AppState` struct. Shared resources are registered as
  `web::Data<SqlitePool>` and `web::Data<Config>`.
- There is NO `src/models.rs` module. Model/payload structs are defined
  inline in each handler file.
- The wrapper-shared `<wrapper>/.env` is loaded by `src/config.rs`
  (`Config::from_env()` + `load_dotenv()`) so `DATABASE_URL` and the JWT
  vars are identical to every other backend in the project.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Rust client module for each sibling backend the new service
   should call. The client must read the sibling's URL from
   `std::env::var("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Integration tests (`tests/integration.rs`) that exercise the
   cross-service flows end-to-end via the wrapper-shared SQLite database
   (and, when sibling backends are present, via the typed clients above).

Coding rules:
- Use `reqwest::blocking` or `ureq` for sibling HTTP calls. If neither
  is in `Cargo.toml`, use `std::process::Command` to call `curl` as a
  fallback — do NOT add new crate dependencies.
- Read JWT material via `state.config.jwt_secret` / `state.config.jwt_*`.
  NEVER hardcode the secret. NEVER re-read from `std::env::var` in
  handler code.
- Use `serde::{{Deserialize, Serialize}}` for response/request structs.
- Use `#[cfg(test)]` or a dedicated `tests/` directory for integration
  tests. Guard sibling calls with a helper that returns
  `Result<(), String>` and skips (prints to stderr + returns Ok) when
  the env var is missing or the sibling is unreachable.
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
        "Integration phase: writes src/integrations/mod.rs, "
        "src/integrations/sibling_clients.rs, and tests/integration.rs, "
        "then runs the test-and-fix loop via "
        "`cargo test --test integration 2>&1 || ./test`."
    ),
    "test_command": "cargo test --test integration 2>&1 || ./test",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "src/integrations/mod.rs",
            "language": "rust",
            "description": "src/integrations/mod.rs — integration module root",
            "prompt": """\
Create `src/integrations/mod.rs` as the module root for cross-service
integration code.

Required content:
- A module-level doc comment: "Cross-service integration clients for
  the {service_label} service."
- `pub mod sibling_clients;`
- Re-export the public items: `pub use sibling_clients::*;`

Output the full file contents only.
""",
        },
        {
            "path": "src/integrations/sibling_clients.rs",
            "language": "rust",
            "description": "src/integrations/sibling_clients.rs — typed HTTP clients for sibling backends",
            "prompt": """\
Write `src/integrations/sibling_clients.rs`. The module exposes one
typed client struct per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Use `std::process::Command` to shell out to `curl` for HTTP calls
  (keeps the dependency list unchanged). If `reqwest::blocking` or
  `ureq` are available in `Cargo.toml`, prefer them instead.
- Each sibling backend gets a struct named `<PascalSlug>Client`.
  The struct:
    - Reads its base URL from
      `std::env::var("SERVICE_URL_<UPPER_SLUG>")` in `new()`. Returns
      `Err(IntegrationError::EnvMissing(...))` when the env var is
      missing.
    - Stores an optional `token: Option<String>`; when set, every
      request sends `Authorization: Bearer <token>`.
    - Exposes `list_items(&self) -> Result<Vec<serde_json::Value>,
      IntegrationError>` and `get_state(&self, key: &str) ->
      Result<serde_json::Value, IntegrationError>` methods that hit
      the sibling's wrapper-shared `/api/items` and
      `/api/state/<key>` endpoints.
- Define a `#[derive(Debug)] pub enum IntegrationError` with
  variants: `EnvMissing(String)`, `HttpError(String)`,
  `ParseError(String)`.
- Implement `std::fmt::Display` and `std::error::Error` for
  `IntegrationError`.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationError` enum and an empty
  `// No sibling clients — {sibling_count} siblings discovered.`
  comment. Do NOT define dummy client structs for non-existent
  siblings.

Output the full file contents only.
""",
        },
        {
            "path": "tests/integration.rs",
            "language": "rust",
            "description": "tests/integration.rs — cross-service integration tests",
            "prompt": """\
Write `tests/integration.rs`. Integration tests that exercise the new
`{service_label}` service end-to-end and (when sibling backends are
present) verify the cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use `#[test]` functions (synchronous). If async is needed, use
  `#[tokio::test]` only when tokio is in dev-dependencies.
- Guard sibling client calls: wrap instantiation in a helper that
  checks the env var and prints a skip message to stderr + returns
  early when the var is missing or the service is unreachable.
- Use `std::process::Command` to call `curl` or `sqlite3` for HTTP
  and DB assertions if `reqwest` is not available.

Required tests:

1. `test_items_endpoint_round_trip` — insert an `Item` row into the
   `items` table via `sqlite3` CLI, then query via the service's
   `/api/items` endpoint (or directly via sqlite3) and assert the row
   exists.

2. `test_react_state_round_trip` — insert a `ReactState` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `test_{items_plural}_endpoint_uses_jwt` — read
   `std::env::var("JWT_SECRET")` and assert it matches
   the value the service would load via `Config::from_env()`.

4. `test_jwt_secret_is_wrapper_shared` — assert that
   `std::env::var("JWT_SECRET").ok()` is `Some(...)` (non-empty).

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `test_sibling_<snake_slug>_items_visible_via_shared_db`.
   Guard with:
   ```rust
   let client = match <PascalSlug>Client::new(None) {{
       Ok(c) => c,
       Err(_) => {{
           eprintln!("SKIP: SERVICE_URL_<SLUG> not set");
           return;
       }}
   }};
   ```
   Then call `client.list_items()` and skip if unreachable.

6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
