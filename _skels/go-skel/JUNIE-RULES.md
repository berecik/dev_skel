# Junie Rules — `go-skel`

JetBrains Junie agent guidance for the `go-skel` skeleton. Mirrors
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
