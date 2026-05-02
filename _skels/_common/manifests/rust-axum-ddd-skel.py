"""AI manifest for the ``rust-axum-ddd-skel`` skeleton.

This manifest exists separately from ``rust-axum-skel.py`` because the
two skeletons disagree on **where source files live**, even though their
HTTP contract is identical.

- ``rust-axum-skel`` (flat) keeps every CRUD handler in
  ``src/handlers/<entity>.rs`` with model structs defined inline, a
  shared ``AppState`` extracted as ``State<Arc<AppState>>``, and one
  ``wrapper_router()`` function in ``src/handlers/mod.rs`` that
  registers every route.
- ``rust-axum-ddd-skel`` follows the canonical FastAPI shape: each
  resource is a self-contained module under ``src/<resource>/`` with
  the file split ``mod.rs`` / ``repository.rs`` / ``adapters/{mod,sql}.rs``
  / ``service.rs`` / ``depts.rs`` / ``routes.rs``. Routes never import
  ``sea_orm`` or ``crate::entities``; services take an
  ``Arc<dyn <Resource>Repository>`` (never ``DatabaseConnection``); the
  adapter is the only file in the resource that imports ``sea_orm::*``.
  Domain errors flow as ``DomainError`` and the HTTP layer maps via
  ``From<DomainError> for ApiError`` + ``IntoResponse for ApiError``.
  ``src/main.rs`` is a slim composition root that builds an
  ``AppContext`` and merges per-resource ``Router``s via
  ``.merge(<resource>::depts::router(ctx.clone(), conn.clone()))``.

Re-using the flat manifest produced AI output that landed in the wrong
place: it created ``src/handlers/<item>.rs`` (which does not exist in
the DDD layout) and tried to extend a ``wrapper_router`` function that
does not exist either. This file replaces that stub with a DDD-aware
prompt set.

See ``_docs/DDD-SKELETONS.md`` for the cross-stack DDD layer rules.
"""

SYSTEM_PROMPT = """\
You are a senior Rust engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton. This skeleton uses the canonical
FastAPI shape adapted to axum: every CRUD resource is a self-contained
module under `src/<resource>/` with a fixed file split.

Project layout (CRITICAL - read carefully):
- The Cargo crate name is `rust-axum-ddd-skel`. NEVER use
  `rust-axum-skel` (that is a different, flat skeleton) or
  `rust-actix-ddd-skel`.
- The Cargo crate root is `{service_subdir}/`. Source lives under
  `src/`. The entry point is `src/main.rs` - a slim composition root
  that calls each resource's `depts::router(ctx, conn)` and merges
  the result into one `/api`-nested `Router`.
- Every resource module follows this layout:
    src/<resource>/
      mod.rs              -- public re-exports (router, repository
                             trait, service, DTOs)
      repository.rs       -- abstract `<Resource>Repository` trait
                             (async-trait, returns Result<T, DomainError>)
      adapters/mod.rs     -- `pub mod sql;`
      adapters/sql.rs     -- SeaORM implementation; THE ONLY file in
                             this resource that imports `sea_orm::*`
                             or `crate::entities`
      service.rs          -- business logic + DTOs (serde structs);
                             holds `Arc<dyn <Resource>Repository>`,
                             never a `DatabaseConnection`
      depts.rs            -- composition root: builds adapter ->
                             service, defines a per-resource
                             `RouterState` with `FromRef` impls, and
                             returns a `Router` with state baked in
                             via `.with_state(state)`
      routes.rs           -- HTTP layer: handlers extract
                             `State<Arc<<Resource>Service>>` plus
                             `AuthUser`; never touch the DB or the
                             entity directly
- The new resource being added is `src/{item_name}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`). The SeaORM entity for `{item_class}` is
  assumed to already exist under `src/entities/<entity>.rs` --
  re-export it from `repository.rs` like the reference does:
    `pub use crate::entities::<entity>::Model as {item_class};`

Layer rules (NON-NEGOTIABLE):
1. Routes never import `sea_orm` or `crate::entities`. They take the
   service via `State<Arc<<Resource>Service>>` and pull the
   authenticated principal via the `AuthUser` extractor - do NOT
   parse `Authorization` headers manually and do NOT use
   `axum::http::HeaderMap` for auth.
2. Services take a repository trait object
   (`Arc<dyn <Resource>Repository>`), NEVER `DatabaseConnection`.
3. The adapter (`adapters/sql.rs`) is the ONLY file in this resource
   that imports `sea_orm::*` or `crate::entities::*`. Other files use
   the abstract trait + the entity re-export from `repository.rs`.
4. DTOs are explicit serde structs in the resource module
   (`Create<Item>Payload` lives in `routes.rs`; service input DTOs
   like `New<Item>DTO` live in `service.rs`).
5. Domain errors flow through `crate::shared::DomainError`. The HTTP
   layer maps them via the existing `From<DomainError> for ApiError`
   and `IntoResponse for ApiError` impls in `crate::shared::httpx` --
   so handlers can `?`-propagate directly into
   `Result<Json<T>, ApiError>`.
6. `depts.rs` is the only place that wires the stack and defines the
   per-resource `RouterState`. `main.rs` calls
   `<resource>::depts::router(ctx.clone(), conn.clone())` and merges
   the result.

Available shared helpers from `crate::shared`:
- `crate::shared::DomainError` -- variants:
  `NotFound(String)`, `Conflict(String)`, `Validation(String)`,
  `Unauthorized(String)`, `Forbidden(String)`,
  `Db(#[from] sea_orm::DbErr)`,
  `Jwt(#[from] jsonwebtoken::errors::Error)`,
  `Password(String)`, `Other(String)`. Service code raises the
  semantic variants directly (e.g.
  `Err(DomainError::Validation("name cannot be empty".to_string()))`).
- `crate::shared::ApiError` -- axum error wrapper that implements
  `IntoResponse`. Convertible from `DomainError`, `sea_orm::DbErr`,
  and `jsonwebtoken::errors::Error` via existing `From` impls.
- `crate::shared::AppContext` -- composition handle defined in
  `src/shared/context.rs`. Fields:
    pub config: Config,
    pub user_repo: Arc<dyn UserRepository>,
  Cloneable; the auth extractor pulls it from any `RouterState` via
  `FromRef<S> for AppContext`.
- `crate::shared::errors::is_unique_violation(err: &sea_orm::DbErr)
  -> bool` -- driver-agnostic UNIQUE-constraint detector. Use inside
  adapters to translate raw SeaORM errors into
  `DomainError::Conflict`.

Auth (JWT):
- The `AuthUser` extractor lives in `crate::auth::AuthUser` (re-exported
  from `crate::auth`). It implements
  `FromRequestParts<S> where S: Send + Sync, AppContext: FromRef<S>`,
  so any per-resource `RouterState` that provides
  `FromRef<RouterState> for AppContext` automatically supports
  `_user: AuthUser` as a handler argument. The extractor reads
  `Authorization: Bearer <token>`, calls `verify_token` against
  `ctx.config.jwt_secret`, and looks up the principal via
  `ctx.user_repo`. Returns `ApiError(DomainError::Unauthorized(...))`
  on failure (= 401). NEVER parse the header yourself.
- The new resource's `depts.rs` MUST define a `RouterState` struct
  with TWO `FromRef` impls:
    impl FromRef<<Resource>RouterState> for Arc<<Resource>Service> {{ ... }}
    impl FromRef<<Resource>RouterState> for AppContext {{ ... }}
  Without the second impl, `_user: AuthUser` will fail to compile.

SeaORM conventions (adapters/sql.rs only):
- Use `EntityTrait::find()` / `find_by_id(id)` / `update_many()` and
  `ActiveModel {{ ..Default::default() }}.insert(self.db.as_ref())`.
- Wrap missing rows as
  `DomainError::NotFound(format!("{item_name} {{id}} not found"))`.
- Wrap unique-constraint failures via
  `if shared::errors::is_unique_violation(&err) {{ DomainError::Conflict(...) }}`.
- Use `chrono::Utc::now()` for timestamps. The entity carries
  `created_at` / `updated_at` columns of type `DateTime<Utc>`.
- The entity columns + types are defined in `src/entities/<entity>.rs`;
  assume the entity already exists -- do NOT add or modify entities.

JSON shape (wrapper-shared contract):
- All keys are `snake_case` via serde defaults / explicit
  `#[serde(rename_all = "snake_case")]` when needed.
- Datetimes use RFC3339 via `chrono::DateTime<Utc>`'s default
  `Serialize` impl.
- Optional / nullable fields use `Option<T>`.

Shared environment (every backend in the wrapper relies on the same
env vars from `<wrapper>/.env`):
- `DATABASE_URL` -- common database (resolved by
  `src/config.rs::Config::from_env()`).
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`.
NEVER call `std::env::var` from a resource module -- the
`AppContext.config` already carries these values.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match indentation (4 spaces), brace style, and import grouping of
  the reference resource (`src/items/`) exactly.
- Group imports as: stdlib block, blank line, third-party block
  (axum / sea_orm / serde / chrono / async_trait), blank line,
  internal block (`crate::...`).
- When `{auth_type}` is `none`, drop the `_user: AuthUser` parameter
  and the `use crate::auth::AuthUser;` import from `routes.rs`. Keep
  the `FromRef<RouterState> for AppContext` impl in `depts.rs` so the
  shape stays uniform (a future flip back to JWT only needs a route
  edit).
- Do NOT introduce new dependencies. The crate already depends on
  `axum`, `tokio`, `serde`, `serde_json`, `chrono`, `sea-orm`,
  `tower`, `tower-http`, `tracing`, `tracing-subscriber`, `dotenvy`,
  `jsonwebtoken`, `argon2`, `async-trait`, and `thiserror`.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""


MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `cargo check` and `cargo build` after generation to "
        "confirm the new src/{item_name}/ module compiles. The "
        "wrapper-shared <wrapper>/.env is wired in via "
        "src/config.rs (Config::from_env()); src/main.rs is the only "
        "file outside src/{item_name}/ that this manifest edits. The "
        "SeaORM entity in src/entities/ is assumed to already exist."
    ),
    "targets": [
        {
            "path": "src/{item_name}/mod.rs",
            "template": "src/items/mod.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/mod.rs -- public re-exports for the "
                "{item_class} resource"
            ),
            "prompt": """\
Create `src/{item_name}/mod.rs` for the `{item_class}` resource.

This file is the resource's public face: it declares the sub-modules
and re-exports the names callers will reach for. It does NOT contain
any logic of its own.

Required contents:
- Module-level `//!` doc comment summarising the resource (e.g.
  "{item_class} resource - `/api/{items_plural}`. Canonical CRUD
  example.") plus a one-line summary of each layer's role, mirroring
  the reference's tone.
- `pub mod adapters;`
- `pub mod depts;`
- `pub mod repository;`
- `pub mod routes;`
- `pub mod service;`
- Re-exports (each prefixed with `#[allow(unused_imports)]`):
    `pub use depts::router;`
    `pub use repository::{{{item_class}Repository, New{item_class}}};`
    `pub use service::{{{item_class}Service, New{item_class}DTO}};`

REFERENCE (`src/items/mod.rs` -- adapt the structure for
`{item_class}`; the reference defines the canonical re-export shape):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/repository.rs",
            "template": "src/items/repository.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/repository.rs -- abstract repository "
                "trait for {item_class}"
            ),
            "prompt": """\
Create `src/{item_name}/repository.rs`. This file declares the
storage abstraction for the `{item_class}` resource. It is the ONLY
file in the resource (besides `adapters/sql.rs`) that names the
SeaORM entity, and it does so via a `pub use` re-export so service
code can name `{item_class}` without importing `crate::entities`.

Required contents:
- Module-level `//!` doc comment (one or two lines).
- `use async_trait::async_trait;`
- `use crate::shared::DomainError;`
- `pub use crate::entities::<entity>::Model as {item_class};` --
  re-export the SeaORM entity's `Model` as the resource's
  `{item_class}` type. The entity module name is the snake_case
  singular of the resource (e.g. `crate::entities::item` for `Item`,
  `crate::entities::pizza` for `Pizza`). Use `{item_name}` as the
  entity module name.
- A `pub struct New{item_class}` insert payload with the user-supplied
  fields the entity needs at create time. Use `String`,
  `Option<String>`, `bool`, `Option<i32>` as appropriate. Derive
  `Debug, Clone`.
- `#[async_trait]` on a `pub trait {item_class}Repository: Send + Sync`
  with async methods returning `Result<T, DomainError>`:
    - `list(&self) -> Result<Vec<{item_class}>, DomainError>`
    - `get(&self, id: i32) -> Result<{item_class}, DomainError>`
    - `create(&self, new: New{item_class}) -> Result<{item_class}, DomainError>`
    - `update(&self, id: i32, patch: New{item_class}) -> Result<{item_class}, DomainError>`
      (skip if the resource truly has no update endpoint)
    - `delete(&self, id: i32) -> Result<(), DomainError>` (skip if no
      delete endpoint)

Do NOT import `sea_orm` here. The entity re-export uses `Model` only.
Routes / services depend on this trait, never on
`DatabaseConnection`.

REFERENCE (`src/items/repository.rs` -- adapt the trait surface for
`{item_class}`; preserve the `pub use crate::entities::...::Model as
{item_class};` pattern):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/adapters/mod.rs",
            "template": "src/items/adapters/mod.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/adapters/mod.rs -- adapters package marker"
            ),
            "prompt": """\
Create `src/{item_name}/adapters/mod.rs`. This file is a one-line
package marker that exposes the SeaORM adapter sub-module.

Required contents (verbatim):
```
pub mod sql;
```

REFERENCE (`src/items/adapters/mod.rs` -- one-line file):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/adapters/sql.rs",
            "template": "src/items/adapters/sql.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/adapters/sql.rs -- SeaORM "
                "implementation of {item_class}Repository"
            ),
            "prompt": """\
Create `src/{item_name}/adapters/sql.rs`. This is the ONLY file in
the `{item_name}` resource that imports `sea_orm::*` or
`crate::entities::*`.

Required contents:
- Module-level `//!` doc comment (one line, e.g. "SeaORM-backed
  implementation of `{item_class}Repository`.").
- Imports:
  - `std::sync::Arc`
  - `async_trait::async_trait`
  - `chrono::Utc`
  - `sea_orm::{{ActiveModelTrait, DatabaseConnection, EntityTrait,
    QueryOrder, Set}}` (add `ColumnTrait`, `QueryFilter`,
    `sea_query::Expr` only if you actually use them; do NOT pull in
    unused imports).
  - `crate::entities::<entity>` (use `{item_name}` as the entity
    module name).
  - `crate::{item_name}::repository::{{{item_class}, {item_class}Repository, New{item_class}}}`
  - `crate::shared::DomainError`
- `#[derive(Clone)] pub struct Sea{item_class}Repository {{ db: Arc<DatabaseConnection> }}`.
- `impl Sea{item_class}Repository {{ pub fn new(db: Arc<DatabaseConnection>) -> Self {{ Self {{ db }} }} }}`.
- `#[async_trait] impl {item_class}Repository for Sea{item_class}Repository {{ ... }}` with:
  - `list` -- `<entity>::Entity::find().order_by_desc(<entity>::Column::CreatedAt).order_by_desc(<entity>::Column::Id).all(self.db.as_ref()).await?`.
  - `get` -- `<entity>::Entity::find_by_id(id).one(self.db.as_ref()).await?`; map `None` to
    `Err(DomainError::NotFound(format!("{item_name} {{id}} not found")))`.
  - `create` -- build an `<entity>::ActiveModel {{ ..Default::default() }}` with the
    fields from `New{item_class}` plus `created_at: Set(now)` and
    `updated_at: Set(now)`, then `.insert(self.db.as_ref()).await?`.
  - `update` (if declared) -- fetch via `find_by_id`, mutate the
    `ActiveModel`, set `updated_at = Set(Utc::now())`, then `.update(...)`.
  - `delete` (if declared) -- `<entity>::Entity::delete_by_id(id).exec(self.db.as_ref()).await?`;
    when `result.rows_affected == 0`, return `DomainError::NotFound`.

Use `Utc::now()` (returning `DateTime<Utc>`) for timestamps -- match
the entity column type rather than formatting a string. Use
`crate::shared::errors::is_unique_violation(&err)` to translate UNIQUE
violations into `DomainError::Conflict(...)` when an insert can race.

REFERENCE (`src/items/adapters/sql.rs` -- adapt every line for
`{item_class}`, preserving structure, error wrapping, and import
ordering):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/service.rs",
            "template": "src/items/service.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/service.rs -- business logic over "
                "{item_class}Repository"
            ),
            "prompt": """\
Create `src/{item_name}/service.rs`. This is the resource's
business-logic layer.

Required contents:
- Module-level `//!` doc comment matching the reference's tone.
- Imports:
  - `std::sync::Arc`
  - `crate::{item_name}::repository::{{{item_class}, {item_class}Repository, New{item_class}}}`
  - `crate::shared::DomainError`
- `#[derive(Debug, Clone)] pub struct New{item_class}DTO` -- input
  shape for `create`. Decoupled from the entity so the route's
  payload type and the service's input shape are independent.
- `#[derive(Clone)] pub struct {item_class}Service {{ repo: Arc<dyn {item_class}Repository> }}`.
- `impl {item_class}Service {{ pub fn new(repo: Arc<dyn {item_class}Repository>) -> Self {{ Self {{ repo }} }} }}`.
- Async methods returning `Result<T, DomainError>`:
  - `list(&self) -> Result<Vec<{item_class}>, DomainError>` --
    delegate to `self.repo.list()`.
  - `get(&self, id: i32) -> Result<{item_class}, DomainError>` --
    delegate to `self.repo.get(id)`.
  - `create(&self, dto: New{item_class}DTO) -> Result<{item_class}, DomainError>`
    -- validate non-empty required fields and return
    `DomainError::Validation("...".to_string())` on bad input. Then
    translate the DTO into `New{item_class}` and call
    `self.repo.create(...)`.
  - `update(&self, id: i32, dto: New{item_class}DTO) -> Result<{item_class}, DomainError>`
    -- only include if the repository declares `update`.
  - `delete(&self, id: i32) -> Result<(), DomainError>` -- only
    include if the repository declares `delete`.

The service translates DTOs into entity-shaped values, calls the
repository, and returns domain errors directly. Routes are
responsible for turning those errors into HTTP statuses via the
existing `From<DomainError> for ApiError` impl.

NEVER hold a `DatabaseConnection` here. NEVER import `sea_orm` here.

REFERENCE (`src/items/service.rs`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/depts.rs",
            "template": "src/items/depts.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/depts.rs -- composition root: builds "
                "{item_class}Service and returns a Router"
            ),
            "prompt": """\
Create `src/{item_name}/depts.rs`. This is the ONLY place in the
resource that wires the adapter into the service and exposes the
per-resource `Router`.

Required contents:
- Module-level `//!` doc comment matching the reference's tone.
- Imports:
  - `std::sync::Arc`
  - `axum::{{extract::FromRef, routing::{{get, post}}, Router}}`
    (add `put` / `delete` only if the route table declares them).
  - `sea_orm::DatabaseConnection`
  - `crate::{item_name}::adapters::sql::Sea{item_class}Repository`
  - `crate::{item_name}::repository::{item_class}Repository`
  - `crate::{item_name}::routes::{{...}}` -- import every handler
    function the router registers below.
  - `crate::{item_name}::service::{item_class}Service`
  - `crate::shared::AppContext`
- `#[derive(Clone)] pub struct {item_class}RouterState {{ pub service: Arc<{item_class}Service>, pub ctx: AppContext, }}`.
- TWO `FromRef` impls (BOTH are required for `_user: AuthUser` to
  compile inside this resource's handlers):
    impl FromRef<{item_class}RouterState> for Arc<{item_class}Service> {{
        fn from_ref(input: &{item_class}RouterState) -> Self {{ input.service.clone() }}
    }}
    impl FromRef<{item_class}RouterState> for AppContext {{
        fn from_ref(input: &{item_class}RouterState) -> Self {{ input.ctx.clone() }}
    }}
- `pub fn build_service(conn: Arc<DatabaseConnection>) -> {item_class}Service`
  that constructs `Sea{item_class}Repository` -> `Arc<dyn {item_class}Repository>`
  -> `{item_class}Service::new(repo)`.
- `pub fn router(ctx: AppContext, conn: Arc<DatabaseConnection>) -> Router`
  that:
    1. Builds `let service = Arc::new(build_service(conn));`.
    2. Builds `let state = {item_class}RouterState {{ service, ctx }};`.
    3. Registers routes via `.route("/{items_plural}", get(list_{items_plural}).post(create_{item_name}))` etc.
       Use route paths under `/{items_plural}` and `/{items_plural}/:id` (NOT
       `/api/...` -- the `/api` prefix is added in `main.rs` via
       `.nest("/api", api)`).
    4. Calls `.with_state(state)` once at the end.

REFERENCE (`src/items/depts.rs` -- adapt every name for
`{item_class}`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/{item_name}/routes.rs",
            "template": "src/items/routes.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/routes.rs -- HTTP layer for "
                "/api/{items_plural}"
            ),
            "prompt": """\
Create `src/{item_name}/routes.rs`. This is the HTTP layer for the
`{item_class}` resource. It NEVER imports `sea_orm` or
`crate::entities` -- it only ever names types from
`crate::{item_name}::service` plus `crate::shared::ApiError`.

Required contents:
- Module-level `//!` doc comment matching the reference.
- Imports:
  - `std::sync::Arc`
  - `axum::{{extract::{{Path, State}}, http::StatusCode, response::IntoResponse, Json}}`
  - `serde::Deserialize`
  - `crate::auth::AuthUser`  (drop when `{auth_type}` is `none`)
  - `crate::{item_name}::service::{{{item_class}Service, New{item_class}DTO}}`
  - `crate::shared::ApiError`
- A `#[derive(Debug, Deserialize)] pub struct Create{item_class}Payload`
  for incoming request bodies, with `#[serde(default)]` on optional
  fields.
- Async handlers returning `Result<impl IntoResponse, ApiError>`:
  - `list_{items_plural}(State(svc): State<Arc<{item_class}Service>>, _user: AuthUser) -> Result<impl IntoResponse, ApiError>`.
  - `create_{item_name}(State(svc): State<Arc<{item_class}Service>>, _user: AuthUser, Json(payload): Json<Create{item_class}Payload>) -> Result<impl IntoResponse, ApiError>`
    -- on success returns `(StatusCode::CREATED, Json(inserted))`.
  - `get_{item_name}(State(svc): State<Arc<{item_class}Service>>, _user: AuthUser, Path(id): Path<i32>) -> Result<impl IntoResponse, ApiError>`.
  - Optional `update_{item_name}` / `delete_{item_name}` if the
    service exposes those methods.
- Each handler:
  - Parses Payload -> DTO inline, then calls EXACTLY ONE service
    method.
  - Returns `Json(value)` or `(StatusCode::CREATED, Json(value))`.
  - Lets `?` propagate `DomainError` -> `ApiError` via the existing
    `From<DomainError> for ApiError` impl. Do NOT match on
    `DomainError` variants here.
- When `{auth_type}` is `none`: drop the `_user: AuthUser` parameter
  from every handler and remove the `use crate::auth::AuthUser;`
  import.

REFERENCE (`src/items/routes.rs` -- preserve handler signature shape,
the `Json(payload)` extraction pattern, and the `(StatusCode::CREATED,
Json(...))` return for `create`):
---
{template}
---

Output only the file's contents.
""",
        },
        {
            "path": "src/main.rs",
            "template": "src/main.rs",
            "language": "rust",
            "description": (
                "src/main.rs -- wire {item_class} resource into the "
                "composition root"
            ),
            "prompt": """\
Rewrite `src/main.rs` to wire the new `{item_class}` resource into
the composition root.

CRITICAL CONSTRAINTS:
- Reproduce the EXISTING `src/main.rs` content verbatim except for
  the two additions described below. Do NOT remove any existing
  module declarations, imports, services, or `.merge(...)` calls.
- Preserve the import ordering (stdlib block, blank line, third-party
  block, blank line, internal `crate::...` block).
- Keep the `#[cfg(test)] mod tests {{ ... }}` block at the bottom of
  the file unchanged.

Two minimal additions:

1. Add `mod {item_name};` to the module declarations at the top of
   the file, alphabetised among the existing
   `mod auth; mod catalog; mod categories; ...` entries.

2. Inside the `let api = Router::new()` chain, add ONE line that
   merges the new resource's router. Insert it among the existing
   `.merge(...)` calls (e.g. right after the `items::depts::router`
   merge). The line is:

       .merge({item_name}::depts::router(ctx.clone(), conn.clone()))

   The final `.merge(orders::depts::router(ctx, conn))` line keeps
   passing the un-cloned `ctx` and `conn` so the move semantics of
   the existing chain remain valid.

Everything else -- `index` / `health` handlers, the test module, the
`tracing_subscriber` setup, the `connect_and_init` call, the
`AppContext::new` call, the `seed::seed_default_accounts` call --
stays unchanged.

REFERENCE (`src/main.rs` -- current content; reproduce with only the
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
# ``rust-axum-skel.py``'s integration manifest but with paths and prompt
# text updated for the DDD layout (no ``handlers/mod.rs`` -- we describe
# the per-resource module convention instead).


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Rust engineer integrating a freshly generated Axum
service into an existing dev_skel multi-service wrapper. The service
uses the DDD per-resource layout: each CRUD resource lives under
`src/<resource>/` with the file split (mod / repository /
adapters/sql / service / depts / routes).

The new service is `{service_label}` (slug `{service_slug}`, tech
`rust-axum-ddd-skel`). It already ships:
- The wrapper-shared `Item` resource at `src/items/` mounted at
  `/api/items` (see the reference resource module for the canonical
  layout).
- Wrapper-shared `Category`, `Order`, `Catalog`, and `State`
  resources, each in its own `src/<resource>/` module.
- A user-chosen `{item_class}` module under `src/{item_name}/` mounted
  at `/api/{items_plural}` (the per-target manifest added it).
- JWT auth via `AuthUser` extracted from any per-resource
  `RouterState` that implements `FromRef<RouterState> for AppContext`.
  The JWT secret comes from `Config` (the wrapper-shared secret --
  NEVER re-read from `std::env::var` in resource code).
- `crate::shared` exports the sentinel domain error type
  (`DomainError` + variants `NotFound`, `Conflict`, `Validation`,
  `Unauthorized`, `Forbidden`, `Db`, `Jwt`, `Password`, `Other`) plus
  the `ApiError` axum error wrapper, the `AppContext` composition
  handle, and the `Repository` / `AbstractUnitOfWork` traits.
- Crate name is `rust-axum-ddd-skel`. The wrapper-shared
  `<wrapper>/.env` is loaded by `src/config.rs` (`Config::from_env()`
  + `load_dotenv()`) so `DATABASE_URL` and the JWT vars are identical
  to every other backend in the project.
- DB driver is SeaORM with the SQLite/Postgres dialects. No
  `sea_orm::*` imports in routes / services -- only adapters.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Rust client module (under `src/integrations/`) for each
   sibling backend the new service should call. Each client must read
   the sibling's URL from
   `std::env::var("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Integration tests (`tests/integration.rs`) that exercise the
   cross-service flows end-to-end via the wrapper-shared SQLite
   database (and, when sibling backends are present, via the typed
   clients above).

Coding rules:
- Use `std::process::Command` to shell out to `curl` for sibling HTTP
  calls (keeps the dependency list unchanged). Do NOT add new crate
  dependencies.
- Read JWT material via `Config::from_env()`. NEVER hardcode the
  secret. NEVER re-read `std::env::var("JWT_SECRET")` in resource
  code.
- Use `serde::{{Deserialize, Serialize}}` for request/response
  structs.
- Use a dedicated `tests/` directory for integration tests. Guard
  sibling calls with a helper that returns `Result<(), String>` and
  skips (prints to stderr + returns Ok) when the env var is missing
  or the sibling is unreachable.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items` and
  `/api/{items_plural}` endpoints. Do not assume sibling services
  exist; gracefully degrade.

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
            "description": "src/integrations/mod.rs -- integration module root",
            "prompt": """\
Create `src/integrations/mod.rs` as the module root for cross-service
integration code.

Required content:
- A module-level `//!` doc comment: "Cross-service integration clients
  for the {service_label} service."
- `pub mod sibling_clients;`
- Re-export the public items: `pub use sibling_clients::*;`

Output the full file contents only.
""",
        },
        {
            "path": "src/integrations/sibling_clients.rs",
            "language": "rust",
            "description": (
                "src/integrations/sibling_clients.rs -- typed HTTP "
                "clients for sibling backends"
            ),
            "prompt": """\
Write `src/integrations/sibling_clients.rs`. The module exposes one
typed client struct per sibling backend in the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Use `std::process::Command` to shell out to `curl` for HTTP calls
  (keeps the dependency list unchanged).
- Each sibling backend gets a struct named `<PascalSlug>Client`. The
  struct:
    - Reads its base URL from
      `std::env::var("SERVICE_URL_<UPPER_SLUG>")` in `new()`. Returns
      `Err(IntegrationError::EnvMissing(...))` when the env var is
      missing.
    - Stores an optional `token: Option<String>`; when set, every
      request sends `Authorization: Bearer <token>`.
    - Exposes `list_items(&self) -> Result<Vec<serde_json::Value>, IntegrationError>`
      and `get_state(&self, key: &str) -> Result<serde_json::Value, IntegrationError>`
      methods that hit the sibling's wrapper-shared `/api/items` and
      `/api/state/<key>` endpoints.
- Define a `#[derive(Debug)] pub enum IntegrationError` with
  variants: `EnvMissing(String)`, `HttpError(String)`,
  `ParseError(String)`.
- Implement `std::fmt::Display` and `std::error::Error` for
  `IntegrationError`.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationError` enum and an empty
  `// No sibling clients -- {sibling_count} siblings discovered.`
  comment. Do NOT define dummy client structs for non-existent
  siblings.

Output the full file contents only.
""",
        },
        {
            "path": "tests/integration.rs",
            "language": "rust",
            "description": "tests/integration.rs -- cross-service integration tests",
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
  and DB assertions.

Required tests:

1. `test_items_endpoint_round_trip` -- insert an `Item` row into the
   `items` table via `sqlite3` CLI, then query the data back (or via
   the service's `/api/items` endpoint when running) and assert the
   row exists.

2. `test_react_state_round_trip` -- insert a `state` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `test_{items_plural}_endpoint_uses_jwt` -- read
   `std::env::var("JWT_SECRET")` and assert it is non-empty (the
   service reads it via `Config::from_env()`).

4. `test_jwt_secret_is_wrapper_shared` -- assert that
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
