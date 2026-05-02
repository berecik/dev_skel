"""AI manifest for the ``rust-actix-ddd-skel`` skeleton.

This manifest exists separately from ``rust-actix-skel.py`` because the
two skeletons disagree on **where source files live**, even though their
HTTP contract is identical.

- ``rust-actix-skel`` (flat) keeps every CRUD handler in
  ``src/handlers/<entity>.rs`` with inline payload structs and a single
  shared ``handlers::register`` function wiring routes inline. The
  database is reached through a globally-registered
  ``web::Data<SqlitePool>`` and there is no DDD layering.
- ``rust-actix-ddd-skel`` follows the canonical FastAPI shape: each
  resource is a self-contained module under ``src/<resource>/`` with the
  six-file split ``mod.rs`` / ``repository.rs`` /
  ``adapters/{mod.rs,sql.rs}`` / ``service.rs`` / ``depts.rs`` /
  ``routes.rs``. Routes never touch SeaORM; services take a
  ``Repository`` trait object (never ``DatabaseConnection``); the
  adapter is the only file in the resource that imports ``sea_orm``.
  Domain errors flow through ``crate::shared::DomainError`` and the
  HTTP layer relies on the ``ResponseError`` impl on that enum.

Re-using the flat manifest produced AI output that landed in the wrong
place: it tried to create ``src/handlers/<item>.rs`` (which does not
exist in the DDD layout) and to extend a ``handlers::register``
function that does not exist either. This file replaces that stub with
a DDD-aware prompt set.

See ``_docs/DDD-SKELETONS.md`` for the cross-stack DDD layer rules.
"""

SYSTEM_PROMPT = """\
You are a senior Rust engineer regenerating one source file inside the
dev_skel `{skeleton_name}` skeleton. This skeleton uses the canonical
FastAPI shape: every CRUD resource is a self-contained module under
`src/<resource>/` with a fixed six-file split.

Project layout (CRITICAL — read carefully):
- The Cargo crate name is `rust-actix-ddd-skel`. NEVER use
  `rust-actix-skel` (that is a different, flat skeleton). Inside the
  crate, sibling modules are reached via `crate::*` (e.g.
  `crate::shared`, `crate::auth`, `crate::entities`, `crate::config`).
- The Cargo crate root is `{service_subdir}/`. Source lives under
  `src/`. The entry point is `src/main.rs` — a slim composition root
  that wires every resource module via per-resource `register_routes`
  callbacks.
- Every resource module follows this layout:
    src/<resource>/
      mod.rs                  -- public re-exports + sub-module decls
      repository.rs           -- abstract trait
      adapters/mod.rs         -- `pub mod sql;`
      adapters/sql.rs         -- SeaORM impl (only file importing sea_orm)
      service.rs              -- business logic, takes a Repository
      depts.rs                -- composition root: register_routes(cfg, conn)
      routes.rs               -- HTTP layer: pulls service, never touches DB
- The new resource being added is `src/{item_name}/`.
- The CRUD entity is `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).
- The SeaORM entity for `{item_class}` already exists in
  `src/entities/{item_name}.rs`. Do NOT add or modify entities --
  the `entities/` directory is consolidated and shared.

Layer rules (NON-NEGOTIABLE):
1. Routes never import `sea_orm` and never import
   `crate::entities::*`. They take the service via
   `web::Data<{item_class}Service>` (or whatever the service type is
   called in this module) and call exactly one method on it.
2. Services take a repository trait object
   (`Arc<dyn {item_class}Repository + Send + Sync>` or `Arc<dyn
   {item_class}Repository>` matching the existing items service),
   NEVER `DatabaseConnection`. The service never imports `sea_orm`.
3. The adapter (`adapters/sql.rs`) is the ONLY file in the resource
   that imports `sea_orm::*` and `crate::entities::{item_name}::*`.
4. DTOs are explicit `serde` structs declared inside the resource
   module (typically in `service.rs` or `routes.rs`). Don't return
   `entity::{item_name}::Model` as the public service surface --
   re-export it via `pub use` from the repository module the same way
   `items::repository` does (`pub use crate::entities::item::Model as
   Item;`) if you need a domain alias.
5. Domain errors flow through `crate::shared::DomainError`. Throw the
   sentinel; the HTTP layer translates to status codes via the
   `ResponseError` impl already on the enum.
6. `depts.rs` is the only place that wires adapter -> service ->
   `app_data` -> route scope.

Available shared helpers from `crate::shared` (verified by reading
`src/shared/{{errors,httpx,repository}}.rs`):
- `DomainError` enum with these EXACT variants (use them verbatim --
  do NOT invent new variants):
    NotFound(String) -> 404
    Conflict(String) -> 409
    Validation(String) -> 400
    Unauthorized(String) -> 401
    Forbidden(String) -> 403
    Db(#[from] sea_orm::DbErr) -> 500   // adapters bubble via `?`
    Jwt(#[from] jsonwebtoken::errors::Error) -> 401
    Password(String) -> 500
    Other(String) -> 500
- `DomainError::other(err)` -- helper that wraps an
  `impl std::fmt::Display` payload as `Other(...)`.
- `is_unique_violation(&sea_orm::DbErr) -> bool` (in
  `shared::errors`) -- driver-agnostic UNIQUE-constraint detector;
  adapters use it to translate raw DbErr into
  `DomainError::Conflict(...)`.
- `shared::httpx::error_response(status, detail)` -- canonical
  `{{detail, status}}` envelope helper. Routes typically don't need
  it because the `ResponseError` impl on `DomainError` does the right
  thing automatically when a handler returns
  `Result<HttpResponse, DomainError>`.
- `shared::Repository<T, Id>` -- generic CRUD trait declared for
  symmetry with go-skel / FastAPI; per-resource modules declare their
  own narrower trait instead, so the new module follows the items
  pattern (declare a resource-specific `{item_class}Repository`
  trait, do NOT implement `shared::Repository`).

Auth (JWT):
- The `AuthUser` extractor lives at `crate::auth::AuthUser`. Adding
  `_user: AuthUser` to a handler's parameter list automatically
  enforces JWT auth -- the extractor reads
  `Authorization: Bearer <token>`, calls `verify_token` against the
  wrapper-shared `Config`, looks up the principal via the boxed
  `users::UserRepository` registered in `app_data`, and returns
  `DomainError::Unauthorized(...)` (-> 401) on any failure.
- The new module's `register_routes` does NOT take a JWT layer
  parameter. Auth is route-level via the extractor. Match the items
  signature exactly:
    `pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>)`.
- Inside a handler, `_user: AuthUser` (or `user: AuthUser` if you
  need the principal) gives you `id: i64` and `username: String`.
- When `{auth_type}` is `none`, drop the `_user: AuthUser` parameter
  AND drop `use crate::auth::AuthUser;`. Route paths stay the same.

SeaORM conventions (adapters/sql.rs only):
- Use `entity::Entity::find_by_id(id).one(self.db.as_ref()).await?`
  for single-row lookups; wrap `Ok(None)` as
  `DomainError::NotFound(format!("{item_name} {{id}} not found"))`.
- Use `entity::Entity::find().order_by_desc(...).all(...).await?`
  for `list`.
- Use `entity::ActiveModel {{ ..., ..Default::default() }}.insert(...)`
  for `create`. Convert chrono `Utc::now()` into `Set(...)` for
  `created_at` / `updated_at`.
- Use `existing.into() -> ActiveModel` then `.update(...)` for
  partial updates -- mirror `items::adapters::sql::complete`.
- Use `entity.delete(self.db.as_ref()).await?` for delete; if you
  need to detect "not found" wrap accordingly via `find_by_id` first.
- Errors propagate via `From<DbErr> for DomainError` automatically --
  use `?` and let the conversion happen. Use `is_unique_violation`
  ONLY when you specifically want to translate a UNIQUE failure
  into `DomainError::Conflict(...)`.
- Datetime fields: `chrono::DateTime<Utc>` (verified by reading
  `src/entities/item.rs`). Serialize as RFC3339 by default.

JSON shape (wrapper-shared contract):
- All keys are `snake_case`. Use `#[serde(rename_all = "snake_case")]`
  at the struct level on DTOs, OR per-field `#[serde(rename = "...")]`
  -- whichever matches the items pattern in this skeleton.
- Foreign keys land as `category_id` (not `category`).
- Datetimes use `chrono::DateTime<Utc>` (RFC3339 by default).
- Optional / nullable FKs use `Option<i32>`.

Shared environment (every backend in the wrapper relies on the same
env vars from `<wrapper>/.env`):
- `DATABASE_URL` -- common database (resolved by
  `crate::config::Config::from_env()`).
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`.
NEVER call `std::env::var` from a resource module -- the JWT helpers
read the wrapper-shared `Config` registered as `web::Data<Config>` in
`main.rs`.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match the indentation (4 spaces), brace style, and import ordering
  of the reference resource (`src/items/`) exactly.
- Group imports as: stdlib block (`std::*`), blank line, third-party
  block (`actix_web`, `async_trait`, `chrono`, `sea_orm`, `serde`,
  ...), blank line, internal block (`crate::*`).
- Do NOT introduce new dependencies. Available crates: `actix-web`,
  `actix-rt`, `tokio`, `serde`, `serde_json`, `tracing`,
  `tracing-actix-web`, `dotenvy`, `sea-orm`, `sea-orm-migration`,
  `jsonwebtoken`, `argon2`, `password-hash`, `rand`, `chrono`,
  `thiserror`, `futures-util`, `async-trait`.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""


MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `cargo check` and `cargo build --release` after generation "
        "to confirm the new src/{item_name}/ module compiles. The "
        "wrapper-shared <wrapper>/.env is wired in via src/config.rs; "
        "src/main.rs is the only file outside src/{item_name}/ that "
        "this manifest edits. The SeaORM entity for {item_class} is "
        "assumed to already exist in src/entities/{item_name}.rs."
    ),
    "targets": [
        {
            "path": "src/{item_name}/mod.rs",
            "template": "src/items/mod.rs",
            "language": "rust",
            "description": (
                "src/{item_name}/mod.rs -- public re-exports + "
                "sub-module declarations for the {item_class} resource"
            ),
            "prompt": """\
Create `src/{item_name}/mod.rs` for the `{item_class}` resource.

This file is the resource's module root. It declares every sub-module
and re-exports the public surface so callers (mainly `main.rs`) can
write `use crate::{item_name}::register_routes;` instead of reaching
into the sub-modules directly.

Required contents:
- A doc comment matching the reference's tone (one paragraph
  describing the resource and its `/api/{items_plural}` HTTP surface,
  followed by a bulleted breakdown of each layer's responsibility).
- Sub-module declarations (alphabetical, mirror the reference):
    pub mod adapters;
    pub mod depts;
    pub mod repository;
    pub mod routes;
    pub mod service;
- Re-exports of the public surface:
    pub use depts::register_routes;
    #[allow(unused_imports)]
    pub use repository::{{{item_class}Repository, New{item_class}}};
    #[allow(unused_imports)]
    pub use service::{{{item_class}Service, New{item_class}DTO}};

If you also expose a response DTO (e.g. `{item_class}Dto`), add it to
the `service::` re-export line. The `#[allow(unused_imports)]`
attributes are there because not every binary in the workspace
consumes every re-export -- keep them.

REFERENCE (`src/items/mod.rs` -- adapt every line for `{item_class}`,
preserving the doc-comment shape and the `pub mod` ordering):
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
                "src/{item_name}/repository.rs -- abstract "
                "{item_class}Repository trait + insert payload"
            ),
            "prompt": """\
Create `src/{item_name}/repository.rs`. This file declares the abstract
`{item_class}Repository` trait that `adapters/sql.rs` implements and
that `service.rs` depends on.

Required contents:
- A short module-level doc comment matching the reference's tone
  (one sentence: "`{item_class}Repository` -- storage abstraction for
  the {item_name} resource.").
- Imports:
    use async_trait::async_trait;

    use crate::shared::DomainError;
- A `pub use` re-export of the SeaORM entity model as a domain alias:
    pub use crate::entities::{item_name}::Model as {item_class};
  (The reference does this so callers can refer to a domain type
  without leaking SeaORM into their import lines. The adapter still
  reaches `crate::entities::{item_name}::Entity` directly.)
- A `New{item_class}` insert-payload struct (plain struct, no serde
  derives -- it's an internal repository input shape, not an HTTP
  payload):
    #[derive(Debug, Clone)]
    pub struct New{item_class} {{
        pub <field>: <type>,
        ...
    }}
  Mirror the entity's required columns: include every NOT NULL field
  except `id`, `created_at`, `updated_at` (those are repository
  responsibilities). For the items reference these are `name`,
  `description`, `is_completed`, `category_id`. Adapt the field list
  to whatever the `{item_class}` entity declares -- assume sensible
  defaults if you cannot infer them.
- The trait itself:
    #[async_trait]
    pub trait {item_class}Repository: Send + Sync {{
        async fn list(&self) -> Result<Vec<{item_class}>, DomainError>;
        async fn get(&self, id: i32) -> Result<{item_class}, DomainError>;
        async fn create(&self, new: New{item_class}) -> Result<{item_class}, DomainError>;
        async fn update(&self, id: i32, patch: New{item_class}) -> Result<{item_class}, DomainError>;
        async fn delete(&self, id: i32) -> Result<(), DomainError>;
    }}
  Use `i32` as the primary-key type (matches every other resource in
  this skeleton). If `{item_class}` semantically benefits from
  domain-specific methods (e.g. `complete` on items, `submit` on
  orders), add them to the trait alongside the standard CRUD set.

REFERENCE (`src/items/repository.rs` -- the canonical shape; adapt
every name and field):
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
Create `src/{item_name}/adapters/sql.rs`. This is the ONLY file in the
`{item_name}` resource that imports `sea_orm::*` and
`crate::entities::{item_name}::*`. The companion `adapters/mod.rs`
already exists in the items reference and contains nothing more than
`pub mod sql;` -- you do NOT need to emit it; the manifest's mod.rs
target re-emits the resource layout. (If `adapters/mod.rs` is missing
on disk, the per-resource skel scaffold creates it from the items
template.)

Required contents:
- A short doc comment: "SeaORM-backed implementation of
  `{item_class}Repository`."
- Imports (preserve the reference's grouping -- stdlib / third-party /
  internal):
    use std::sync::Arc;

    use async_trait::async_trait;
    use chrono::Utc;
    use sea_orm::sea_query::Expr;     // only if you need col_expr updates
    use sea_orm::{{
        ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait,
        QueryFilter, QueryOrder, Set,
    }};

    use crate::entities::{item_name};
    use crate::{item_name}::repository::{{
        {item_class}, {item_class}Repository, New{item_class},
    }};
    use crate::shared::DomainError;
- A struct holding the connection handle:
    #[derive(Clone)]
    pub struct Sea{item_class}Repository {{
        db: Arc<DatabaseConnection>,
    }}

    impl Sea{item_class}Repository {{
        pub fn new(db: Arc<DatabaseConnection>) -> Self {{
            Self {{ db }}
        }}
    }}
- A full `#[async_trait] impl {item_class}Repository for Sea{item_class}Repository`
  block implementing every trait method:
    - `list` -> `{item_name}::Entity::find().order_by_desc({item_name}::Column::CreatedAt).order_by_desc({item_name}::Column::Id).all(self.db.as_ref()).await?`
    - `get` -> `find_by_id(id).one(self.db.as_ref()).await?`, mapping
      `Ok(None)` to `DomainError::NotFound(format!("{item_name} {{id}} not found"))`.
    - `create` -> build an `{item_name}::ActiveModel {{ ..., ..Default::default() }}`
      from the `New{item_class}` payload, set `created_at` / `updated_at` to
      `Utc::now()`, and call `.insert(self.db.as_ref()).await?`.
    - `update` -> `find_by_id(id).one(...).await?` -> `existing.into()` -> mutate
      fields from the `New{item_class}` patch -> set `updated_at = Utc::now()` ->
      `.update(self.db.as_ref()).await?`. Map missing rows to
      `DomainError::NotFound(...)`.
    - `delete` -> `find_by_id(id).one(...).await?` -> map missing to
      `DomainError::NotFound(...)` -> `.delete(self.db.as_ref()).await?` ->
      `Ok(())`.
- Errors propagate via `?` thanks to `From<DbErr> for DomainError`.
  Only translate manually when you specifically want a different
  variant (e.g. `is_unique_violation` -> `DomainError::Conflict`).

REFERENCE (`src/items/adapters/sql.rs` -- adapt every line for
`{item_class}`; preserve the import grouping, the `Sea<X>Repository`
naming convention, and the SeaORM call shape):
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
                "src/{item_name}/service.rs -- {item_class}Service "
                "with DTOs and business logic over {item_class}Repository"
            ),
            "prompt": """\
Create `src/{item_name}/service.rs`. This is the resource's
business-logic layer.

Required contents:
- A short doc comment: "Service-layer logic for `/api/{items_plural}`.
  Holds an `Arc<dyn {item_class}Repository>` -- never a
  `DatabaseConnection`."
- Imports (NEVER import `sea_orm` here):
    use std::sync::Arc;

    use serde::{{Deserialize, Serialize}};

    use crate::{item_name}::repository::{{
        {item_class}, {item_class}Repository, New{item_class},
    }};
    use crate::shared::DomainError;
- DTOs (serde structs with snake_case JSON keys via
  `#[serde(rename_all = "snake_case")]` at the struct level):
    `New{item_class}DTO`     -- create input shape (mirrors the
                                fields the user can supply at create
                                time).
    `{item_class}Update`     -- update input shape (use Option<...>
                                for partial updates if you want PATCH
                                semantics, otherwise mirror New<X>DTO
                                for full replacement).
    `{item_class}Dto`        -- response shape only if you need a
                                projection distinct from the entity.
                                If the entity already serialises
                                cleanly (it does for items via the
                                `Serialize` derive on the SeaORM
                                Model), skip this struct -- the
                                reference returns the entity directly.
- The service struct:
    #[derive(Clone)]
    pub struct {item_class}Service {{
        repo: Arc<dyn {item_class}Repository>,
    }}

    impl {item_class}Service {{
        pub fn new(repo: Arc<dyn {item_class}Repository>) -> Self {{
            Self {{ repo }}
        }}

        pub async fn list(&self) -> Result<Vec<{item_class}>, DomainError> {{
            self.repo.list().await
        }}

        pub async fn get(&self, id: i32) -> Result<{item_class}, DomainError> {{
            self.repo.get(id).await
        }}

        pub async fn create(&self, dto: New{item_class}DTO) -> Result<{item_class}, DomainError> {{
            // Validate non-empty required text fields up front. Wrap
            // bad input in DomainError::Validation(...).
            // Then translate the DTO into a New{item_class} payload
            // and delegate to the repository.
            ...
        }}

        pub async fn update(&self, id: i32, patch: {item_class}Update) -> Result<{item_class}, DomainError> {{
            // Optional: re-fetch via repo.get(id), apply non-None
            // patch fields, persist via repo.update. Match whichever
            // shape your repo trait declared.
            ...
        }}

        pub async fn delete(&self, id: i32) -> Result<(), DomainError> {{
            self.repo.delete(id).await
        }}
    }}

The service translates DTOs into repository inputs, calls the
repository, and returns domain errors. Routes are responsible for
turning those errors into HTTP statuses via the `ResponseError` impl
on `DomainError`.

REFERENCE (`src/items/service.rs` -- shows the canonical service
shape, including `NewItemDTO`, the `Arc<dyn ItemRepository>` field,
and the validation-then-delegate body):
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
                "src/{item_name}/depts.rs -- composition root: "
                "register_routes(cfg, conn)"
            ),
            "prompt": """\
Create `src/{item_name}/depts.rs`. This is the ONLY place in the
resource that wires the adapter into the service and registers the
HTTP routes with actix-web.

Required contents:
- A short doc comment: "Composition seam for the `{item_name}`
  resource. `register_routes` wires a `Sea{item_class}Repository` into
  a `{item_class}Service`, registers it via `app_data`, and mounts
  `/{items_plural}` under the parent scope."
- Imports:
    use std::sync::Arc;

    use actix_web::web;
    use sea_orm::DatabaseConnection;

    use crate::{item_name}::adapters::sql::Sea{item_class}Repository;
    use crate::{item_name}::repository::{item_class}Repository;
    use crate::{item_name}::routes::*;     // or list each handler explicitly
    use crate::{item_name}::service::{item_class}Service;
- A `build_service` helper (mirrors the items reference) so other
  compositions can reuse the wiring without re-mounting routes:
    pub fn build_service(conn: Arc<DatabaseConnection>) -> {item_class}Service {{
        let repo: Arc<dyn {item_class}Repository> =
            Arc::new(Sea{item_class}Repository::new(conn));
        {item_class}Service::new(repo)
    }}
- The `register_routes` entry point. The signature MUST be exactly:
    pub fn register_routes(cfg: &mut web::ServiceConfig, conn: Arc<DatabaseConnection>) {{
        let svc = build_service(conn);
        cfg.app_data(web::Data::new(svc)).service(
            web::scope("/{items_plural}")
                .service(list_{items_plural})
                .service(create_{item_name})
                .service(get_{item_name})
                .service(update_{item_name})
                .service(delete_{item_name}),
        );
    }}
  Adjust the `.service(...)` list to match whatever handlers
  `routes.rs` actually declares -- every `#[get/#[post/#[put/#[delete]`
  handler in `routes.rs` must appear here exactly once. Do NOT
  accept a JWT layer parameter -- auth is route-level via the
  `AuthUser` extractor.

REFERENCE (`src/items/depts.rs` -- preserve the `build_service` +
`register_routes` split, the `Arc<DatabaseConnection>` parameter
type, and the `web::scope("/items")` mount pattern):
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
                "src/{item_name}/routes.rs -- actix handlers for "
                "/api/{items_plural}"
            ),
            "prompt": """\
Create `src/{item_name}/routes.rs`. This is the HTTP layer for the
`{item_class}` resource. It NEVER imports `sea_orm` and NEVER imports
`crate::entities::*`.

Required contents:
- A short doc comment: "HTTP handlers for `/api/{items_plural}`.
  Thin: parse -> call `{item_class}Service` -> translate `DomainError`
  via the shared `ResponseError` impl."
- Imports:
    use actix_web::{{delete, get, post, put, web, HttpResponse}};
    use serde::Deserialize;

    use crate::auth::AuthUser;            // omit when {auth_type} == none
    use crate::{item_name}::service::{{
        {item_class}Service, New{item_class}DTO, {item_class}Update,
    }};
    use crate::shared::DomainError;
- A small private payload struct per write endpoint that needs one,
  decorated with `#[derive(Debug, Deserialize)]` and snake_case JSON
  keys. Mirror the items reference's `CreateItemPayload` -- field
  defaults via `#[serde(default)]` for optional fields, no rename
  attribute (snake_case is the natural Rust style here).
- One async handler function per endpoint:
    #[get("")]
    pub async fn list_{items_plural}(
        svc: web::Data<{item_class}Service>,
        _user: AuthUser,
    ) -> Result<HttpResponse, DomainError> {{
        let rows = svc.list().await?;
        Ok(HttpResponse::Ok().json(rows))
    }}

    #[post("")]
    pub async fn create_{item_name}(
        svc: web::Data<{item_class}Service>,
        _user: AuthUser,
        payload: web::Json<Create{item_class}Payload>,
    ) -> Result<HttpResponse, DomainError> {{
        let p = payload.into_inner();
        let inserted = svc.create(New{item_class}DTO {{ ... }}).await?;
        Ok(HttpResponse::Created().json(inserted))
    }}

    #[get("/{{id}}")]
    pub async fn get_{item_name}(
        svc: web::Data<{item_class}Service>,
        _user: AuthUser,
        path: web::Path<i32>,
    ) -> Result<HttpResponse, DomainError> {{
        let id = path.into_inner();
        let item = svc.get(id).await?;
        Ok(HttpResponse::Ok().json(item))
    }}

    #[put("/{{id}}")]
    pub async fn update_{item_name}(
        svc: web::Data<{item_class}Service>,
        _user: AuthUser,
        path: web::Path<i32>,
        payload: web::Json<Update{item_class}Payload>,
    ) -> Result<HttpResponse, DomainError> {{
        let id = path.into_inner();
        let updated = svc.update(id, {item_class}Update {{ ... }}).await?;
        Ok(HttpResponse::Ok().json(updated))
    }}

    #[delete("/{{id}}")]
    pub async fn delete_{item_name}(
        svc: web::Data<{item_class}Service>,
        _user: AuthUser,
        path: web::Path<i32>,
    ) -> Result<HttpResponse, DomainError> {{
        let id = path.into_inner();
        svc.delete(path.into_inner()).await?;
        Ok(HttpResponse::NoContent().finish())
    }}

Rules:
- The function-name set MUST line up with the `.service(...)` list in
  `depts.rs` -- every handler appears in both files exactly once.
- Always return `Result<HttpResponse, DomainError>` so the
  `ResponseError` impl on `DomainError` does the status mapping.
- When `{auth_type}` is `none`, drop the `_user: AuthUser` parameter
  AND drop `use crate::auth::AuthUser;`. Route paths stay the same.
- Use `web::Path<i32>` for path-id extractors (matches the items
  reference and the `i32` primary key in the entity).

REFERENCE (`src/items/routes.rs` -- preserve the
`CreateItemPayload`-style payload-struct shape, the
`Result<HttpResponse, DomainError>` return type, and the
`svc.<method>(...).await?` -> `HttpResponse::Xxx().json(...)`
handler structure):
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
Rewrite `src/main.rs` to wire the new `{item_class}` resource into the
composition root.

CRITICAL CONSTRAINTS:
- Reproduce the EXISTING `src/main.rs` content verbatim except for
  the two minimal additions described below. Do NOT remove any
  existing `mod` declarations, services, `register_routes` calls,
  tracing setup, seed calls, or test functions.
- Preserve the import ordering (stdlib block, blank line, third-party
  block, blank line, internal `crate::*` block).

Two minimal additions:

1. Add a `mod {item_name};` declaration alongside the other resource
   modules near the top of the file. Keep the alphabetical ordering
   already used by the existing block (`mod auth; mod catalog; mod
   categories; mod config; mod db; mod entities; mod items; mod
   orders; mod seed; mod shared; mod state; mod users;`).

2. Add ONE line inside the `App::new().configure(...)` chain in the
   `HttpServer::new(move || {{ ... }})` closure, after the existing
   `.configure(|c| orders::register_routes(c, conn.clone()))` call:

       .configure(|c| {item_name}::register_routes(c, conn.clone()))

   The new line must come AFTER the orders configure (or at the end
   of the chain if orders is already last) and use the exact same
   `conn.clone()` capture pattern as the surrounding lines.

The tracing setup, seed plumbing, `index` / `health` handlers,
`ProjectInfo` / `HealthResponse` structs, and the `#[cfg(test)]`
module all stay unchanged.

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
# ``rust-actix-skel.py``'s integration manifest with paths and prompt
# text updated for the DDD layout (no flat ``handlers/`` -- we describe
# the per-resource module convention instead).


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Rust engineer integrating a freshly generated
Actix-web service into an existing dev_skel multi-service wrapper. The
service uses the DDD per-resource layout: each CRUD resource lives
under `src/<resource>/` with the six-file split (mod / repository /
adapters/{{mod,sql}} / service / depts / routes).

The new service is `{service_label}` (slug `{service_slug}`, tech
`rust-actix-ddd-skel`). It already ships:
- The wrapper-shared `Item` resource at `src/items/` mounted at
  `/api/items` (the canonical DDD reference module).
- Wrapper-shared `Category`, `Order`, `Catalog`, and `State`
  resources, each in its own `src/<resource>/` module.
- A user-chosen `{item_class}` module under `src/{item_name}/` mounted
  at `/api/{items_plural}` (the per-target manifest added it).
- JWT auth via the `AuthUser` extractor at `crate::auth::AuthUser`.
  The extractor reaches the wrapper-shared `Config` and the boxed
  `users::UserRepository` via `app_data`; resource code never calls
  `std::env::var` for JWT material.
- `crate::shared` exports the sentinel domain errors (`DomainError`
  with `NotFound / Conflict / Validation / Unauthorized / Forbidden /
  Db / Jwt / Password / Other` variants), the `is_unique_violation`
  helper, and the `error_response` HTTP envelope helper.
- Crate name is `rust-actix-ddd-skel`. The wrapper-shared
  `<wrapper>/.env` is loaded by `src/config.rs`
  (`Config::from_env()` + `load_dotenv()`) so `DATABASE_URL` and the
  JWT vars are identical to every other backend in the project.
- DB driver is SeaORM (`sqlx-sqlite` + `sqlx-postgres` features).
  Resource code never uses raw `sqlx` queries.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Rust client module (under `src/integrations/`) for each
   sibling backend the new service should call. Each client must
   read the sibling's URL from
   `std::env::var("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. Integration tests (`tests/integration.rs`) that exercise the
   cross-service flows end-to-end via the wrapper-shared SQLite
   database (and, when sibling backends are present, via the typed
   clients above).

Coding rules:
- Use `std::process::Command` to shell out to `curl` for HTTP calls
  if `reqwest::blocking` or `ureq` are not in `Cargo.toml`. Do NOT
  add new crate dependencies.
- Read JWT material via the wrapper-shared `Config::from_env()`.
  NEVER hardcode the secret. NEVER call
  `std::env::var("JWT_SECRET")` in resource code.
- Use `serde::{{Deserialize, Serialize}}` for request/response
  structs.
- Use `#[test]` (synchronous) for integration tests; only use
  `#[tokio::test]` if tokio is in `[dev-dependencies]`. Guard sibling
  client calls with a helper that returns `Result<(), String>` and
  skips (prints to stderr + returns Ok) when the env var is missing
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
  and DB assertions if `reqwest` is not available.

Required tests:

1. `test_items_endpoint_round_trip` -- insert an `Item` row into the
   `items` table via `sqlite3` CLI, then query via the service's
   `/api/items` endpoint (or directly via sqlite3) and assert the row
   exists.

2. `test_react_state_round_trip` -- insert a `ReactState` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `test_{items_plural}_endpoint_uses_jwt` -- read
   `std::env::var("JWT_SECRET")` and assert it matches
   the value the service would load via `Config::from_env()`.

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
