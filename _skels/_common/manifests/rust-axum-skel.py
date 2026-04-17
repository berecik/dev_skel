"""AI manifest for the ``rust-axum-skel`` skeleton.

The skeleton ships a minimal Axum service with `index` / `health`
handlers and the wrapper-shared `Config` (in `src/config.rs`) carried
inside `AppState`. This manifest tells ``_bin/skel-gen-ai`` how to add
a `{item_class}` CRUD module — a `models` file, a `handlers` file, and
an updated `main.rs` that registers the new routes — all while
preserving the existing config plumbing.

Mirrors the structure of ``rust-actix-skel.py``; the only differences
are Axum's `Router` / `State` API instead of Actix's `App::new` /
`web::Data`.
"""

SYSTEM_PROMPT = """\
You are a senior Rust engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Cargo crate root is `{service_subdir}/`. Source lives under
  `src/`. The existing entry point is `src/main.rs` and the
  wrapper-shared `Config` lives in `src/config.rs`.
- The crate already depends on `axum`, `tokio`, `serde`, `serde_json`,
  `tower`, `tower-http`, `tracing`, `tracing-subscriber`, and
  `dotenvy`. Do NOT add new dependencies.
- The reference handlers (`index`, `health`) live in `main.rs` and
  pull the wrapper-shared `Config` out of `State<Arc<AppState>>`. The
  new handlers MUST follow the same pattern.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The DB table for the new entity MUST be
  named `{items_plural}` (this matches the dev_skel shared-DB
  integration test convention).

Shared environment (CRITICAL — every backend service in the wrapper
relies on the same env vars from `<wrapper>/.env`):
- `DATABASE_URL` — common database. Read it via `state.config.database_url`
  (already populated by `Config::from_env()` in `src/config.rs`).
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL` — also exposed via `state.config.jwt_*`. NEVER
  re-read them from `std::env::var` in handler code.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match the indentation, brace style, and import order of the
  REFERENCE templates exactly.
- Use `serde::{{Deserialize, Serialize}}` for the model struct.
- Use `axum::{{extract::{{Path, State}}, http::StatusCode, response::IntoResponse,
  routing::{{get, post}}, Json, Router}}` for handlers.
- Async functions returning `impl IntoResponse` (or
  `Result<Json<T>, StatusCode>` when an error path exists).
- Error handling: log via `tracing::error!` and return
  `StatusCode::INTERNAL_SERVER_ERROR` on failure. NEVER panic.
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
            "path": "src/models.rs",
            "template": None,
            "language": "rust",
            "description": "src/models.rs — `{item_class}` struct + helpers",
            "prompt": """\
Create `src/models.rs` defining the `{item_class}` model used by the
new CRUD handlers.

Required content:
- A `pub struct {item_class}` with these fields (all `pub`):
  - `id: i64`
  - `name: String`
  - `description: Option<String>`
  - `is_completed: bool`
  - `created_at: String` (ISO 8601 timestamp)
  - `updated_at: String`
- Derive `Debug, Clone, serde::Serialize, serde::Deserialize`.
- A `pub struct New{item_class}` (used for incoming POST bodies) with:
  - `pub name: String`
  - `pub description: Option<String>`
  - `pub is_completed: Option<bool>`
- Derive `Debug, serde::Deserialize` on `New{item_class}`.
- Add a one-line module-level doc comment explaining that this module
  represents rows in the wrapper-shared `{items_plural}` table.

Imports: `use serde::{{Deserialize, Serialize}};` only.

Output only the file's contents.
""",
        },
        {
            "path": "src/handlers/{item_name}.rs",
            "template": None,
            "language": "rust",
            "description": "src/handlers/{item_name}.rs — Axum handlers for `{item_class}`",
            "prompt": """\
IMPORTANT: The handlers directory is a MODULE DIRECTORY with
`src/handlers/mod.rs` (NOT a single `src/handlers.rs` file). You are
creating a NEW sub-module at `src/handlers/{item_name}.rs`. Do NOT
create `src/handlers.rs` — that would conflict with the existing
`src/handlers/mod.rs`.

Create `src/handlers/{item_name}.rs` with Axum handlers for the `{item_class}`
entity. The handlers form a tiny CRUD layer mounted under
`/api/{items_plural}`.

Required content:
- Module-level doc comment: "CRUD handlers for the wrapper-shared
  `{items_plural}` table. Reads `DATABASE_URL` via
  `state.config.database_url`."
- Imports:
  ```rust
  use std::sync::Arc;
  use axum::{{extract::{{Path, State}}, http::StatusCode,
              response::IntoResponse, Json}};

  use crate::models::{{New{item_class}, {item_class}}};
  use crate::AppState;
  ```
- A small private helper `fn db_path(state: &Arc<AppState>) ->
  Option<std::path::PathBuf>` that converts the
  `state.config.database_url` (`sqlite:///...`) into a filesystem path
  relative to the wrapper directory (the parent of the service dir).
  Return `None` if the URL is not sqlite — handlers should respond
  with `StatusCode::NOT_IMPLEMENTED` in that case.
- Three handlers:
  - `pub async fn list_{items_plural}(State(state):
    State<Arc<AppState>>) -> Result<Json<Vec<{item_class}>>,
    StatusCode>` — opens the sqlite file via stdlib
    `std::process::Command` invoking `sqlite3 <path> "SELECT id, name,
    description, is_completed, created_at, updated_at FROM
    {items_plural}"` and parses the pipe-delimited output into
    `Vec<{item_class}>`. (The skeleton intentionally avoids the
    `rusqlite` crate to keep the dependency list unchanged; users can
    swap to `rusqlite` later.)
  - `pub async fn get_{item_name}(State(state): State<Arc<AppState>>,
    Path(id): Path<i64>) -> Result<Json<{item_class}>, StatusCode>` —
    same approach, returns `StatusCode::NOT_FOUND` when missing.
  - `pub async fn create_{item_name}(State(state):
    State<Arc<AppState>>, Json(payload): Json<New{item_class}>) ->
    Result<(StatusCode, Json<{item_class}>), StatusCode>` — runs
    `sqlite3 <path> "INSERT INTO ..."` and returns
    `(StatusCode::CREATED, Json(row))`.
- All handlers respect the auth contract:
  - When `{auth_type}` is `none`: no token check.
  - For any other `{auth_type}`: at the top of each mutating handler
    (POST), inspect the `Authorization` header (extracted via an
    additional `axum::http::HeaderMap` parameter) and confirm it
    starts with `Bearer `. Return `StatusCode::UNAUTHORIZED` when
    missing. Use `state.config.jwt_secret` only as a placeholder for
    the real verification — production wiring is left to the user.
    NEVER re-read JWT material from `std::env::var`.

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

Required transformations:
- Add `pub mod {item_name};` to the module declarations.
- In the `wrapper_router()` function, add new `.route(...)` lines for
  `/api/{items_plural}` (GET list + POST create) and
  `/api/{items_plural}/:id` (GET retrieve).
  Use `{item_name}::list_{items_plural}`, `{item_name}::create_{item_name}`,
  `{item_name}::get_{item_name}`.
- Keep every other line of the REFERENCE EXACTLY as-is — do NOT remove
  the existing `auth`, `categories`, `items`, `state` routes.
- The function must compile with `cargo check`.

REFERENCE (`src/handlers/mod.rs`):
---
{template}
---
""",
        },
    ],
}


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Rust engineer integrating a freshly generated Axum
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`rust-axum-skel`). It already ships:
- The wrapper-shared `Item` model + handlers mounted at `/api/items`
  using rusqlite + serde against the shared `DATABASE_URL`.
- The wrapper-shared `ReactState` model + handlers mounted at `/api/state`
  and `/api/state/{{key}}`.
- A user-chosen `{item_class}` model + handlers (the per-target manifest
  rewrote `Item` to `{item_class}` for this run).
- JWT auth via the `AuthUser` extractor from `AppState` — the secret
  comes from `state.config.jwt_secret` (the wrapper-shared secret —
  NEVER re-read from `std::env::var` in handler code).
- The wrapper-shared `<wrapper>/.env` is loaded by `src/config.rs`
  (`Config::from_env()` + `load_dotenv()`) so `DATABASE_URL` and the JWT
  vars are identical to every other backend in the project.
- Axum idioms: `State<Arc<AppState>>` for shared state, `Router` for
  route registration, `axum::extract::{{Path, State}}` for extractors.

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
