# Agents Rules

Authoritative rules and onboarding guide for all AI agents (LLM assistants)
working on the `dev_skel` project. This file complements `_docs/JUNIE-RULES.md`
and `_docs/LLM-MAINTENANCE.md`. When rules differ, follow the most restrictive
guidance unless the user explicitly overrides it.

`/CLAUDE.md` mirrors this file for Claude Code and adds Claude-specific
operational notes; the rules below apply to all agents regardless of which
entrypoint loads them.

---

## 1. Read These Files First (in order)

1. `/AGENTS.md` (this file) — or `/CLAUDE.md` if you are Claude Code
2. `_docs/JUNIE-RULES.md` (project-authoritative rules)
3. `_docs/LLM-MAINTENANCE.md` (operational guide and workflows)
4. `_docs/README.md` (documentation index)

When working on a specific skeleton (for example `python-fastapi-skel`), also
load:

5. `_skels/<name>/AGENTS.md` (if present) or `_skels/<name>/CLAUDE.md`
6. `_skels/<name>/JUNIE-RULES.md`
7. The skeleton page in `_docs/` (e.g. `_docs/python-fastapi-skel.md`)

Refresh these files whenever the user says rules/docs changed or after you make
rule-affecting edits.

---

## 2. Project Purpose and Your Role

- Makefile-based project generator system managing multiple skeletons in
  `_skels/*-skel/`.
- Each skeleton produces a framework-specific service inside a wrapper project.
- The root `Makefile` orchestrates `gen-*` and `test-*` targets; `_bin/skel-gen`
  is a relocatable Python entrypoint that delegates to skeleton-level `gen`
  scripts.
- All `_bin/` CLI tools (`install-dev-skel`, `update-dev-skel`,
  `sync-dev-skel`, `skel-list`, `skel-gen`) are now Python and share helpers
  through `_bin/dev_skel_lib.py`. Treat that module as the single source of
  truth for config loading, project generation, and rsync wrappers.
- After project generation, `skel-gen` renders `_skels/_common/AGENTS.md` (and
  any per-skeleton `AGENTS.md`) with placeholders such as `${project_name}`,
  `${service_dir}`, `${skeleton_name}`, and `${skeleton_doc}` so generated
  projects ship with up-to-date agent rules.

Your responsibilities:
1. Maintain generators and skeletons.
2. Keep dependencies healthy and reasonably current.
3. Preserve developer workflows and ergonomics described in `_docs/`.

`_test_projects/` contains generated outputs for e2e tests. Never hand-edit it.

---

## 3. Directory Responsibilities (quick map)

- `Makefile` (root): entry for generator/test targets.
- `_bin/`: Python CLI tools plus the shared `dev_skel_lib.py` module and the
  `rsync-*-excludes.txt` files used by install/update/sync.
- `_skels/_common/`: shared resources used by every skeleton — currently the
  `common-wrapper.sh` script that scaffolds wrapper-level files and the
  templated `AGENTS.md` rendered into generated projects.
- `_skels/*-skel/`: one directory per skeleton, each with `Makefile`, `gen`,
  `merge`, `test`, `deps`, and `install-deps`; should also provide
  skeleton-specific rules/docs (`AGENTS.md`, `JUNIE-RULES.md`).
- `_docs/`: documentation hub including `LLM-MAINTENANCE.md`, per-skeleton
  guides, and the dependency policy.
- `_test_projects/`: generated test apps only. Test Project Location Rule: any
  temporary/repro/debug projects you generate must live here, not elsewhere.

---

## 4. Rules Model and Updates

### 4.1 Global vs Per-Skeleton

- Global: `/AGENTS.md`, `_docs/JUNIE-RULES.md`, `_docs/LLM-MAINTENANCE.md`.
- Per-skeleton: `_skels/<name>/AGENTS.md` and/or `_skels/<name>/JUNIE-RULES.md`
  plus the skeleton doc in `_docs/`.

Apply all relevant global rules first, then overlay skeleton rules that do not
conflict. If conflicts arise, global rules win unless the user overrides them.

### 4.2 When to Update Rules

Update the appropriate rules/doc files whenever architecture, workflows, or
maintenance procedures change. Keep global changes in `/AGENTS.md` and
`_docs/JUNIE-RULES.md`, skeleton-specific changes in the matching skeleton
files, and operational steps in `_docs/LLM-MAINTENANCE.md`.

---

## 5. Operating Expectations (summary)

- Prefer minimal, surgical changes that solve the immediate issue.
- Write/update tests for non-trivial fixes or features.
- Never modify `_test_projects/` directly; regenerate via the proper skeleton.
- Do not weaken or bypass failing tests.
- Preserve UX of generator commands and scripts.

---

## 6. Maintenance Workflow (default)

Unless the user specifies otherwise:
1. Run generator tests: `make clean-test` then `make test-generators`.
2. Fix all reported failures with minimal, targeted changes; re-run the same
   tests until green.
3. Only after tests are green, adjust rules/docs (global and per-skeleton) to
   reflect behaviour changes.
4. If maintaining a single skeleton, you may limit tests and doc updates to
   that skeleton plus any impacted globals.

---

## 7. Safety and Constraints

1. Avoid broad refactors without explicit user approval.
2. Prefer stable, well-supported dependency updates; avoid changes that risk
   widespread breakage.
3. If you cannot confirm external data (e.g., versions), keep current pins and
   note the limitation in docs/commits.
4. Maintain clarity and consistency with each module/skeleton’s existing style.
5. When in doubt about destructive/backward-incompatible actions, ask the user.

---

## 8. Verification Checklist

- Run relevant `make test-*` targets; for skeleton edits, include skeleton-level
  tests and regeneration of `_test_projects/` as needed.
- Confirm documentation/rules are consistent with the implemented behaviour.
- Leave `_test_projects/` untouched except via regeneration.
