# Junie Rules — `go-ddd-skel`

JetBrains Junie agent guidance for the `go-ddd-skel` skeleton. Mirrors
`AGENTS.md` and `CLAUDE.md`; read those for the full context.

## Hard rules

- The wrapper-shared HTTP contract (`/api/auth/*`, `/api/items`,
  `/api/state`) is the source of truth for the React frontend.
  Schema drift breaks every cross-stack test.
- `internal/config.Config` is the only place that reads from the
  process environment. Handlers consume Config via dependency
  injection.
- The default DB is the wrapper-shared SQLite file; the SQLite path
  in `DATABASE_URL` is resolved against the wrapper directory at
  startup. Do not bypass `normalizeSQLiteURL`.
- The schema is bootstrapped via `CREATE TABLE IF NOT EXISTS` on
  startup. There is no separate migrations step — adding tables
  means editing `internal/db/db.go`.

## Default workflow

1. Edit code under `internal/` (not `_test_projects/...`).
2. Run `make test-go` for the skeleton tests, then
   `make test-react-go` for the cross-stack proof.
3. Update `AGENTS.md` / `CLAUDE.md` / `JUNIE-RULES.md` whenever
   cross-agent rules change.

---

## DDD Layer Rules (this skeleton uses the FastAPI shape)

This is a DDD-flavored sister skeleton. The HTTP contract is identical
to its flat counterpart, but the source layout follows the canonical
FastAPI shape. Every resource (`items`, `categories`, `orders`,
`catalog`, `state`) is a self-contained module with the same
five-file split:

| File | Role |
| --- | --- |
| `models` (or `dto/`) | DTOs only — request/response shapes |
| `repository` | abstract interface (Get/List/Save/Update/Delete) |
| `adapters/sql` | concrete impl — the only file that touches the ORM/connection |
| `service` | business logic, constructed with a repository (never a DB) |
| `depts` | composition root: builds adapter → service |
| `routes` | HTTP layer: pulls the service, calls one method, never touches the DB |

Cross-resource modules:

- `auth/` — flat (not CRUD); depends on `users.UserRepository`.
- `users/` — repo-only; no service, no public routes. Consumed by
  `auth/` and `seed/` only.
- `shared/` — `errors` (DomainError sentinels), `httpx`
  (jsonError + wrapResponse), `repository` (abstract Repository<T,ID>
  + AbstractUnitOfWork).

When editing this skeleton:

1. **Stay in the resource module.** Adding a new endpoint to `items`?
   Edit `items/{models,service,depts,routes,adapters/sql}`. Don't
   reach into another resource's adapter.
2. **Services take repositories, never DB connections.** New
   collaborator? Inject another repository.
3. **Routes never touch the DB.** They call services. The DB import in
   a routes file is a smell.
4. **DTOs are explicit.** Don't return ORM entities from services.
5. **`depts` is the only place that wires the stack.** `main` (or
   the App Router `route` files, or `Application.java`) imports
   `depts`, never adapters.
6. **Domain errors flow through `shared.DomainError`.** Throw the
   sentinel; let the HTTP layer translate to status codes.

Full reference: [`_docs/DDD-SKELETONS.md`](../../_docs/DDD-SKELETONS.md).
