# Agents Rules — `go-ddd-skel`

Authoritative rules for AI agents (Claude Code, Junie, ...) working
on the `go-ddd-skel` skeleton. This file complements
`_docs/JUNIE-RULES.md` and `_docs/LLM-MAINTENANCE.md`. When rules
differ, follow the most restrictive guidance unless the user
explicitly overrides it.


## Mandatory Test Artifact Location

- **Mandatory:** Any testing projects, services, data, or files must be created only under `_test_projects/` (the dedicated directory for generated testing skeletons and related test artifacts).

---

## Maintenance Scenario ("let do maintenance" / "let do test-fix loop")

Use this shared scenario whenever the user asks for maintenance (for example: `let do maintenance` or `let do test-fix loop`).

- **1) Finish the requested implementation scenario first.**
- **2) Run tests for changed scope first**, then run full relevant test suites.
- **3) Test code safety** (security/safety checks relevant to the stack and changed paths).
- **4) Simplify and clean up code** (remove dead code, reduce complexity, keep style consistent).
- **5) Run all relevant tests again** after cleanup.
- **6) Fix every issue found** (tests, lint, safety, build, runtime).
- **7) Repeat steps 2–6 until no issues remain.**
- **8) Only then update and synchronize documentation/rules** (`README`, `_docs/`, skeleton docs, agent instructions) to match final behaviour.

This is the default maintenance/test-fix loop and should be commonly understood across all agent entrypoints.

---

## 1. Read These Files First (in order)

1. `_skels/go-ddd-skel/AGENTS.md` (this file) — or `CLAUDE.md` if you are Claude Code
2. `_skels/go-ddd-skel/JUNIE-RULES.md`
3. `_skels/go-ddd-skel/README.md` (if present)
4. `_docs/go-skel.md` (if present)
5. Global rules: `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Pure-Go HTTP service skeleton built on the standard library
  (`net/http` with the Go 1.22+ method-aware router). Generated
  services live under `<wrapper>/<service_slug>/` (or
  `<wrapper>/service/` when no service name is given).
- Requires Go 1.22+ on PATH (`./deps` checks).
- **Shared env contract** (CRITICAL): `internal/config.Config`
  reads `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`,
  `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL`, `SERVICE_HOST`, and
  `SERVICE_PORT` from the wrapper-shared `<wrapper>/.env` (parent
  dir) and the local `./.env` (service dir). Never call
  `os.Getenv` directly from handler code — go through `Config`.
  The Python-flavoured `sqlite:///<rel>` URL the wrapper writes is
  resolved to an absolute path against the wrapper directory by
  `normalizeSQLiteURL` so multiple services share the same
  `_shared/db.sqlite3`.
- **Wrapper-shared backend contract** (CRITICAL): the React
  frontend's typed fetch client + JWT auth flow consumes:
  - `POST /api/auth/register` → 201 `{user, access, refresh}` (with
    duplicate-username 409 guard)
  - `POST /api/auth/login` → 200 `{access, refresh, user_id, username}`
  - `GET/POST /api/items`, `GET /api/items/{id}`,
    `POST /api/items/{id}/complete` (JWT-protected)
  - `GET /api/state`, `PUT /api/state/{key}`, `DELETE /api/state/{key}`
    (JWT-protected per-user JSON KV)
  Schema mirrors the django-bolt skeleton's `app/models.py` so a
  single `_shared/db.sqlite3` is interchangeable.
- The schema is bootstrapped via `CREATE TABLE IF NOT EXISTS` on
  startup (`internal/db/db.go`) — no separate migrations step.

---

## 3. Operational Notes

1. **Always read the file before editing** any source under
   `internal/` or `main.go`.
2. **Plan dep bumps** that change Go version, `golang-jwt/jwt`,
   `modernc.org/sqlite`, or `golang.org/x/crypto`. Confirm scope
   with the user before editing `go.mod`.
3. **Default validation**:
   ```bash
   make clean-test
   make test-generators
   cd _skels/go-skel && make test
   ```
4. Never hand-edit `_test_projects/test-go-app` — regenerate with
   `make gen-go NAME=_test_projects/<name>`.
5. Keep `go vet ./...` and `go build ./...` clean before declaring
   the change done.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (`./test` and `./build --release`
      both pass for a fresh wrapper).
- [ ] Skeleton-specific tests pass (`make test-go`).
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
- [ ] Cross-stack `make test-react-go` is green (full HTTP exercise +
      vitest smoke + Playwright E2E).

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
