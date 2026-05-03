# Claude Code Rules — `wrapper-skel`

Claude-specific complement to `_skels/wrapper-skel/AGENTS.md` and
`_skels/wrapper-skel/JUNIE-RULES.md`. Read those first.

## Mandatory Test Artifact Location

- **Mandatory:** Any testing projects, services, data, or files must
  be created only under `_test_projects/` (the dedicated directory for
  generated testing skeletons and related test artifacts).

## Maintenance Scenario

Standard test-fix loop applies (see `/CLAUDE.md` §Maintenance Scenario).

## Read these files first

1. `_skels/wrapper-skel/CLAUDE.md` (this file)
2. `_skels/wrapper-skel/AGENTS.md`
3. `_skels/wrapper-skel/JUNIE-RULES.md`
4. `_skels/_common/common-wrapper.sh` — the actual implementation
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`

## Skeleton Snapshot

- `wrapper-skel` is the **project basement template**. It owns the
  wrapper directory + shared layer that every service in a multi-service
  `dev_skel` project sits inside.
- Implementation: this skel's `gen` script is a thin shim that calls
  `_skels/_common/common-wrapper.sh "$MAIN_DIR" "" "$TITLE"` (empty
  `PROJECT_SUBDIR` → wrapper-only mode). The shared shell script is
  the single source of truth for wrapper file emission; both this skel
  and every service skel route through it.
- Two supported flows (see AGENTS.md): wrapper-first (this skel
  alone) and service-driven (a service skel that calls
  `common-wrapper.sh` after creating its service dir). Both produce
  byte-identical wrapper files for the shared parts.

## Claude Operational Notes

1. **Always `Read` before editing** any file under
   `_skels/wrapper-skel/` or `_skels/_common/common-wrapper.sh`. The
   latter is heredoc-soup with several gated sections; surgical edits
   only.
2. **Wrapper layout is shared.** Don't fork wrapper file emission
   into a per-skel `gen` script — extend `common-wrapper.sh` instead.
   Both wrapper-only and service-driven flows must continue to
   produce the same output.
3. **Default validation:**
   ```bash
   make clean-test
   bash _skels/wrapper-skel/test_skel
   make test-gen-wrapper          # if added to the Makefile
   make test-generators           # full smoke
   ```
4. Never hand-edit `_test_projects/test-wrapper-*` — regenerate.
5. Keep `common-wrapper.sh` idempotent on the wrapper-only path AND
   on subsequent service-add calls.

## Verification Checklist

- [ ] `bash _skels/wrapper-skel/test_skel` is green.
- [ ] `make gen-wrapper NAME=_test_projects/<x>` produces the canonical
      wrapper layout (`.env`, `_shared/`, `services`, `project`, `env`,
      `kube`, `docker-compose.yml`, `dev_skel.project.yml`).
- [ ] Layering a service onto a wrapper-only project still works
      (`make gen-fastapi NAME=_test_projects/<x>` succeeds and the
      shared `.env`/`_shared/` is preserved).
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
