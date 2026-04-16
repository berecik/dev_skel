# Claude Code Rules — `go-skel`

Claude-specific complement to `_skels/go-skel/AGENTS.md` and
`_skels/go-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/go-skel/CLAUDE.md` (this file)
2. `_skels/go-skel/AGENTS.md`
3. `_skels/go-skel/JUNIE-RULES.md`
4. `_docs/go-skel.md` (if present)
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Pure-Go HTTP service skeleton built on the standard library
  (`net/http` with the Go 1.22+ method-aware router). Handlers + JWT
  middleware + SQLite schema bootstrap live under `internal/` so the
  module's public API is just the binary entry point.
- `internal/config.Config` resolves `DATABASE_URL`, `JWT_*`, and
  `SERVICE_*` from the wrapper-shared `<wrapper>/.env` (parent dir)
  then the local `./.env`. SQLite URLs of the form
  `sqlite:///<relative>` are auto-rewritten to
  `<wrapper>/<relative>` so every service in the wrapper points at
  the same DB file.
- Wrapper-shared HTTP contract identical to the actix / axum /
  spring / flask skels — see AGENTS.md §2.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file under `internal/`,
   `main.go`, or `go.mod`.
2. **Plan crate version bumps** and confirm scope before touching
   `go.mod`. Default Go version is pinned to 1.22.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/go-skel && make test
   make test-react-go
   ```
4. Never hand-edit `_test_projects/test-go-app` — regenerate with
   `make gen-go NAME=_test_projects/<name>`.
5. Keep `go vet ./...` and `go build ./...` clean before declaring
   the change done.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green.
- [ ] `make test-go` is green (skeleton-level tests).
- [ ] `make test-react-go` is green (cross-stack with React).
- [ ] `make test-shared-db` (when implemented) sees the Go service
      reading the wrapper-shared `_shared/db.sqlite3`.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
