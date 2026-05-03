# JUNIE rules — `wrapper-skel`

Project-authoritative rules for the wrapper-skel template. Aligns
with the project-wide `_docs/JUNIE-RULES.md`.

## Purpose

`wrapper-skel` is the **project basement template**. It generates
the wrapper directory + shared layer (`.env`, `_shared/`,
`docker-compose.yml`, dispatch scripts, project/env/kube helpers)
without requiring any specific service. Service skels can then be
overlaid with `make gen-<service-skel> NAME=<wrapper>`.

## Hard rules

1. **Single source of truth.** Wrapper file emission lives in
   `_skels/_common/common-wrapper.sh`. Both `wrapper-skel/gen` AND
   every per-service skel's `gen` route through it. Do not duplicate.
2. **`common-wrapper.sh` must stay idempotent.** Running it twice
   on the same wrapper (first wrapper-only, then with a service) must
   not lose user edits to `.env`, must not duplicate `docker-compose.yml`
   service entries, and must not clobber existing `.skel_context.json`
   sidecars on sibling services.
3. **No per-service knowledge in the wrapper.** Wrapper-only mode
   (empty `PROJECT_SUBDIR`) must skip every block that references a
   specific service: existence check, docker-compose entry, AI sidecar
   force-overwrite, README references. Use the `<service>` placeholder
   for human-readable text in wrapper-only mode.
4. **Composition is opt-in.** `wrapper-skel` does not assume which
   service skel(s) the user will overlay. The wrapper layout is
   service-agnostic.
5. **Do not introduce new top-level wrapper files** without updating
   both `common-wrapper.sh` (emission) AND `test_skel` (assertion).
6. **Tests are the contract.** A passing `bash test_skel` plus a
   green `make test-generators` is the minimum bar before declaring a
   wrapper-layout change done.

## Workflow

1. Edit `_skels/_common/common-wrapper.sh` (the implementation) for
   any wrapper file change.
2. Run `bash _skels/wrapper-skel/test_skel`.
3. Run `make test-gen-wrapper` (when wired) and `make test-generators`.
4. Run a representative cross-stack test
   (`make test-react-fastapi` etc.) to confirm the wrapper still
   integrates with downstream service skels.
5. Update `wrapper-skel/AGENTS.md` and `wrapper-skel/CLAUDE.md` if
   the contract changed.
