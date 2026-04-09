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
            "path": "src/handlers.rs",
            "template": None,
            "language": "rust",
            "description": "src/handlers.rs — Axum handlers for `{item_class}`",
            "prompt": """\
Create `src/handlers.rs` with Axum handlers for the `{item_class}`
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
- The `Router::new()` builder block must register the new handlers
  alongside the existing `/` and `/health` routes:
  ```rust
  .route("/api/{items_plural}", get(handlers::list_{items_plural}).post(handlers::create_{item_name}))
  .route("/api/{items_plural}/:id", get(handlers::get_{item_name}))
  ```
  You will need to add `use axum::routing::{{get, post}};` (or extend
  the existing axum import block) so the new closures resolve.
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
