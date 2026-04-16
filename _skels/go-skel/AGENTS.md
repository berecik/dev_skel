# Agents Rules — `go-skel`

Authoritative rules for AI agents (Claude Code, Junie, ...) working
on the `go-skel` skeleton. This file complements
`_docs/JUNIE-RULES.md` and `_docs/LLM-MAINTENANCE.md`. When rules
differ, follow the most restrictive guidance unless the user
explicitly overrides it.

---

## 1. Read These Files First (in order)

1. `_skels/go-skel/AGENTS.md` (this file) — or `CLAUDE.md` if you are Claude Code
2. `_skels/go-skel/JUNIE-RULES.md`
3. `_skels/go-skel/README.md` (if present)
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
