# COOKIECUTTER-REFACTOR — standalone migration plan for `dev_skel`

This document is the standalone source of truth for the
**Cookiecutter/Jinja2 migration** in `dev_skel`.

It is intentionally separate from the `skel-backport` command design.
The backport workflow depends on this migration, but it is no longer
planned in the same document. See
[`SKEL_BACKPORT_COMMAND.md`](./SKEL_BACKPORT_COMMAND.md) for the
service-to-template command and RAG workflow.

---

## Scope

This plan covers only the work required to move generator output from
the current bash/string-substitution approach to a Cookiecutter-based
template substrate:

1. Move each skeleton to a first-class Jinja template tree.
2. Move the shared wrapper scaffolding into a shared Cookiecutter
   wrapper template.
3. Preserve existing generator UX and byte-for-byte output where
   practical.
4. Keep `make test-generators` green during the migration.
5. Standardize the generated output enough that later tooling
   (`./ai`, `skel-backport`, React/backend compatibility checks)
   has a stable substrate.

---

## Goals

- Replace ad-hoc `merge`/`gen` substitutions with declarative Jinja
  templates and Cookiecutter hooks.
- Keep `_bin/dev_skel_lib.py` as the orchestration boundary for config,
  slug computation, and generation dispatch.
- Preserve wrapper-level contracts documented in `AGENTS.md`, including
  shared `.env`, shared DB wiring, and generated service naming rules.
- Make it easy for future skeleton maintenance to edit templates
  directly instead of re-deriving shell substitutions.

---

## Non-goals

- This document does **not** define the `skel-backport` runtime, prompt,
  or fix-loop. That now lives in `SKEL_BACKPORT_COMMAND.md`.
- This document does **not** define the generated-service `./ai`
  workflow. That remains in `SERVICE_REFACTOR_COMMAND.md`.
- This document does **not** require all React × backend matrix work to
  land in the same change as the Cookiecutter substrate itself. Those
  compatibility gates can be tracked separately once the generation
  substrate is stable.

---

## Implementation outline

### 1. Create shared Cookiecutter substrate

- Add `_skels/_common/wrapper-template/` as the shared wrapper template.
- Move wrapper-level generated files out of
  `_skels/_common/common-wrapper.sh` heredocs into Jinja templates.
- Keep generated wrapper scripts (`./services`, `./run`, `./test`,
  `./build`, `./stop`, `./install-deps`) behaviourally identical.

### 2. Migrate each skeleton incrementally

- Add `_skels/<name>-skel/cookiecutter/` trees.
- Introduce `cookiecutter.json` per skeleton with the values currently
  derived by `dev_skel_lib` and per-skeleton `gen` scripts.
- Preserve service display-name to slug behaviour via
  `dev_skel_lib.slugify_service_name()`.
- Keep skeleton-specific `AGENTS.md`/`JUNIE-RULES.md` rendering intact.

### 3. Update generator orchestration

- Teach `_bin/skel-gen-static` / `_bin/skel-gen-ai` / shared helpers to
  render from Cookiecutter templates when a skeleton has migrated.
- Keep AI generation flowing through `_bin/skel_rag/` and the manifest
  system.
- Ensure static mode remains deterministic and AI-free.

### 4. Verify parity and ergonomics

- Re-run `make clean-test` and `make test-generators` throughout the
  migration.
- Regenerate `_test_projects/` only via the proper test targets.
- Confirm docs/rules stay aligned with the migrated behaviour.

---

## Primary risks

- Hidden output drift while converting bash substitutions to Jinja.
- Divergence between migrated and not-yet-migrated skeletons during the
  transition.
- Wrapper-template regressions affecting every skeleton at once.
- Over-coupling the migration to future AI/backport work instead of
  keeping the substrate stable first.

---

## Verification

- `make clean-test`
- `make test-generators`
- Any skeleton-specific `make test-*` targets for skeletons touched in a
  given migration slice

---

## Related documents

- `SKEL_BACKPORT_COMMAND.md` — standalone plan for the internal
  RAG-based `skel-backport` command.
- `SERVICE_REFACTOR_COMMAND.md` — standalone plan for generated-service
  `./ai`.
- `_docs/LLM-MAINTENANCE.md` — runtime and maintenance details for the
  current RAG stack.
