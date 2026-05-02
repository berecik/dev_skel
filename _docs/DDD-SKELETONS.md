# DDD Skeleton Family

Five backend skeletons in `dev_skel` ship in two flavors:

| Stack | Original (flat handlers) | DDD-layered |
| --- | --- | --- |
| Go (net/http) | `_skels/go-skel/` | `_skels/go-ddd-skel/` |
| Rust + Actix-web | `_skels/rust-actix-skel/` | `_skels/rust-actix-ddd-skel/` |
| Rust + Axum | `_skels/rust-axum-skel/` | `_skels/rust-axum-ddd-skel/` |
| Next.js (App Router) | `_skels/next-js-skel/` | `_skels/next-js-ddd-skel/` |
| Java + Spring Boot | `_skels/java-spring-skel/` | `_skels/java-spring-ddd-skel/` |

The DDD variants are **independent skeletons** — they coexist with the flat
ones, share no source files, and are generated, tested, and shipped
separately. Both flavors implement the same wrapper-shared HTTP contract
(`/api/auth/*`, `/api/items[/...]`, `/api/categories[/...]`,
`/api/catalog[/...]`, `/api/orders[/...]`, `/api/state[/...]`) so a token
issued by one is accepted by every other backend in the same wrapper.

The DDD flavor follows the **canonical FastAPI shape** already used by
`_skels/python-fastapi-skel/app/example_items/` (models, adapters/sql,
depts, routes, services). Each resource is a self-contained module with
the same five-file layout.

## Generation

```
make gen-go-ddd       NAME=myapp [SERVICE="display name"]
make gen-actix-ddd    NAME=myapp [SERVICE="display name"]
make gen-axum-ddd     NAME=myapp [SERVICE="display name"]
make gen-nextjs-ddd   NAME=myapp [SERVICE="display name"]
make gen-spring-ddd   NAME=myapp [SERVICE="display name"]
```

Static gen via `_bin/skel-gen-static <project> <skel-name>` works
identically (e.g. `_bin/skel-gen-static myapp go-ddd-skel "Items API"`).
The AI gen path (`_bin/skel-gen-ai`) currently delegates to the flat
manifest with a layer-aware notice — full DDD-aware manifests are a
follow-up task.

## Test layers

Each DDD skel is wired through every cross-stack test infrastructure:

```
make test-react-{go,actix,axum,nextjs,spring}-ddd        # React + DDD backend
make test-flutter-{go,actix,axum,nextjs,spring}-ddd      # Flutter + DDD backend
make test-devcontainer-{go,actix,axum,nextjs,spring}-ddd # Docker compose
make test-k8s-react-{go,actix,axum,nextjs,spring}-ddd    # Helm + k3s
```

The `_devcontainer_lib.py` and `_k8s_lib.py` registries
(`_POSTGRES_SKELS`, `_HEALTH_PATHS`, `_SERVICE_PORTS`) include the DDD
skels alongside their flat counterparts. The HTTP contract test (the
27-step `register → login → CRUD → orders workflow → cleanup` flow) is
identical for both flavors.

## Layer rules (apply to every DDD skel)

The five rules below are enforced by the layout itself; deviating from
them defeats the abstraction.

### 1. Each resource owns its repository

Per-resource module structure (Go shown — substitute `.rs` / `.js` /
`.java` per stack):

```
internal/items/
  models.go            -- DTOs (NewItem, ItemUpdate, ItemDto)
  repository.go        -- abstract Repository interface (Get, List, Save, Update, Delete)
  adapters/sql.go      -- concrete impl (the ONLY file that touches the ORM/connection)
  service.go           -- business logic; constructed with a repository, never a DB
  depts.go             -- composition root: builds adapter → service → returns it
  routes.go            -- HTTP layer; calls the service, never the repository
```

The same shape applies to `categories`, `orders`, `catalog`, `state`,
`users`, with stack-specific file extensions and module conventions.

### 2. Services take repositories, never DB connections

```go
// CORRECT
func NewItemsService(repo ItemRepository) *ItemsService { ... }

// WRONG
func NewItemsService(db *gorm.DB) *ItemsService { ... }
```

Cross-resource coordination (e.g. orders that need both
`OrderRepository` + `OrderLineRepository`) takes multiple repositories.
The `shared.UnitOfWork` abstraction is declared for symmetry with the
canonical FastAPI shape but is not yet exercised by any skel — services
operate against the connection that adapters wrap.

### 3. Routes never touch the database

Routes pull a service out of the request scope (or via dependency
injection / module-level singleton built in `depts.go`), call a single
service method, and translate the result to HTTP. They do **not**:

- import the ORM
- import the schema/entities
- import the adapter
- run queries

### 4. DTOs are explicit and separate from entities

`models.go` (or `dto/`) defines hand-shaped request/response structs
with the wire-format keys (`is_completed`, `category_id`, `created_at`,
`updated_at` — snake_case across every backend). Services map between
entity types and DTOs. Returning a raw entity from the service is a
layering violation.

### 5. `depts.go` is the composition seam

Each resource exports one factory that wires adapter → service:

```go
func NewServiceFromDB(db *gorm.DB) *ItemsService {
    repo := adapters.NewGormItemRepository(db)
    return NewItemsService(repo)
}
```

`main.go` (or `Application.java`, or the App Router `route.js` files)
imports only `depts` — never adapters, repositories, or schema. The
test-only seam (mocking a repository) is at the same point.

## Cross-cutting modules

### `auth` is flat, not CRUD

`auth/` is a feature module, not a resource. Its `service.go` depends on
`users.UserRepository` for principal lookup; its middleware factory
takes the repository (not a DB connection). There is no repository or
adapter for auth itself.

### `users` exposes only the repository

`users/` ships an entity + repository, no service, no public routes.
The two consumers are `auth/` (login/register/me) and `seed/`
(default-account bootstrap). Mirrors how the canonical FastAPI skel
treats the user entity.

### `shared/` holds cross-resource abstractions

```
shared/
  errors.go        -- DomainError (kind: NotFound / Conflict / Validation / Unauthorized / Other)
  repository.go    -- Repository<T,ID> interface + AbstractUnitOfWork
  httpx.go         -- jsonError(status, detail), wrapResponse(handler) — translates DomainError → HTTP
```

Every resource throws `DomainError` subclasses (`shared.NotFound`,
`shared.Conflict`, etc.). The HTTP layer catches them centrally and
maps to the right status code: `NotFound → 404`, `Conflict → 409`,
`Validation → 400`, `Unauthorized → 401`, otherwise 500.

## When to use which flavor

- **Flat `*-skel`** — quickest path to a working service; one or two
  files per resource; suitable for prototypes, hackathons, glue
  services, demos. Lower abstraction tax.
- **DDD `*-ddd-skel`** — production services with non-trivial domain
  logic; resources that need explicit invariants, transactional
  boundaries, or independent test seams; teams that want a uniform
  layout across language stacks.

Both flavors interoperate at the wrapper level — you can mix flat and
DDD services in the same project without touching the JWT or DB
contract.
