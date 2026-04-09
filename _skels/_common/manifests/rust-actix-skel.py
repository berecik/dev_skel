"""AI manifest for the ``rust-actix-skel`` skeleton.

The skeleton ships a minimal Actix-web service with `index` / `health`
handlers and the wrapper-shared `Config` (in `src/config.rs`) carried
inside `AppState`. This manifest tells ``_bin/skel-gen-ai`` how to add
a `{item_class}` CRUD module — a `models` file, a `handlers` file, a
`db` helper that uses `rusqlite` against the shared `DATABASE_URL`,
and an updated `main.rs` that registers the new routes — all while
preserving the existing config plumbing.
"""

SYSTEM_PROMPT = """\
You are a senior Rust engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Cargo crate root is `{service_subdir}/`. Source lives under
  `src/`. The existing entry point is `src/main.rs` and the
  wrapper-shared `Config` lives in `src/config.rs`.
- The crate already depends on `actix-web`, `serde`, `serde_json`,
  `tracing`, `tracing-actix-web`, `tokio`, and `dotenvy`. Do NOT add
  new dependencies — the dev_skel test runner does not call `cargo
  add`. If you need a sqlite client, use `rusqlite` and document the
  TODO at the top of the file.
- The reference handlers (`index`, `health`) live in `main.rs` and
  pull the wrapper-shared `Config` out of
  `web::Data<Arc<AppState>>`. The new handlers MUST follow the same
  pattern.
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
- Use `actix_web::{{get, post, web, HttpResponse, Responder}}` for
  handlers.
- Async functions, returning `impl Responder` or `HttpResponse`.
- Error handling: log via `tracing::error!` and return
  `HttpResponse::InternalServerError().body(...)` on failure. NEVER
  panic in handler code.
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
            "path": "src/handlers.rs",
            "template": None,
            "language": "rust",
            "description": "src/handlers.rs — Actix handlers for `{item_class}`",
            "prompt": """\
Create `src/handlers.rs` with Actix-web handlers for the `{item_class}`
entity. The handlers form a tiny CRUD layer mounted under
`/api/{items_plural}`.

Required content:
- Module-level doc comment: "CRUD handlers for the wrapper-shared
  `{items_plural}` table. Reads `DATABASE_URL` via
  `state.config.database_url`."
- Imports:
  ```rust
  use std::sync::Arc;
  use actix_web::{{get, post, web, HttpResponse, Responder}};

  use crate::models::{{New{item_class}, {item_class}}};
  use crate::AppState;
  ```
- A small private helper `fn db_path(state: &Arc<AppState>) ->
  Option<std::path::PathBuf>` that converts the
  `state.config.database_url` (`sqlite:///...`) into a filesystem path
  relative to the wrapper directory (the parent of the service dir).
  Return `None` if the URL is not sqlite — handlers should respond
  with 501 in that case so we keep the test runner happy.
- Three handlers:
  - `#[get("/api/{items_plural}")] pub async fn list_{items_plural}(state: web::Data<Arc<AppState>>) -> impl Responder` —
    opens the sqlite file via stdlib `std::process::Command` invoking
    `sqlite3 <path> "SELECT id, name, description, is_completed,
    created_at, updated_at FROM {items_plural}"` and parses the
    pipe-delimited output into `Vec<{item_class}>`. (The skeleton
    intentionally avoids the `rusqlite` crate to keep the dependency
    list unchanged; users can swap to `rusqlite` later.)
  - `#[get("/api/{items_plural}/{{id}}")] pub async fn
    get_{item_name}(state: web::Data<Arc<AppState>>, path:
    web::Path<i64>) -> impl Responder` — same approach, returns 404
    when the row is missing.
  - `#[post("/api/{items_plural}")] pub async fn create_{item_name}(state:
    web::Data<Arc<AppState>>, body: web::Json<New{item_class}>) ->
    impl Responder` — runs `sqlite3 <path> "INSERT INTO ..."` and
    returns the created row.
- All handlers respect the auth contract:
  - When `{auth_type}` is `none`: no token check.
  - For any other `{auth_type}`: at the top of each mutating handler
    (POST), call a small helper `verify_jwt(state: &Arc<AppState>,
    auth_header: Option<&str>) -> bool` that confirms the
    `Authorization: Bearer ...` header is present and non-empty.
    Return `HttpResponse::Unauthorized().finish()` when the helper
    fails. Use `state.config.jwt_secret` only as a placeholder for the
    real verification — production wiring is left to the user. NEVER
    re-read JWT material from `std::env::var`.
- Handlers must compile with `cargo check`. Use `tracing::info!` for
  routine logs and `tracing::error!` for failures.

Output only the file's contents.
""",
        },
        {
            "path": "src/main.rs",
            "template": "src/main.rs",
            "language": "rust",
            "description": "src/main.rs — register the new {item_class} module",
            "prompt": """\
Rewrite `src/main.rs` to register the new `models` and `handlers`
modules.

Required transformations:
- Add `mod models;` and `mod handlers;` at the top of the file (next
  to the existing `mod config;`).
- The `App::new()` builder block must register the new handlers
  alongside the existing `index` / `health` services:
  ```rust
  .service(handlers::list_{items_plural})
  .service(handlers::get_{item_name})
  .service(handlers::create_{item_name})
  ```
- Keep every other line of the REFERENCE EXACTLY as-is — including
  `load_dotenv()`, `Config::from_env()`, `AppState`, the
  `tracing_subscriber` setup, the bind address computation, the test
  module, and the public re-exports. Reproduce them character-for-character.
- Do NOT touch the `#[cfg(test)]` block at the bottom of the file.

REFERENCE (`src/main.rs`):
---
{template}
---
""",
        },
    ],
}
