# Junie Project Rules

Authoritative rules and onboarding guide for Junie (and other LLM assistants)
working on the `dev_skel` project.

This file is **always loaded first** by Junie when maintaining this
repository. Treat it as the single source of truth for LLM behaviour, then
follow any additional per-skeleton LLM files.

---

## 1. Files Junie Must Read First

When you (Junie) start working on this repository, always load, in order:

1. This file: `_docs/JUNIE-RULES.md`
2. The general LLM maintenance guide: `_docs/LLM-MAINTENANCE.md`
3. The project docs index: `_docs/README.md`

When working on a **specific skeleton** (for example `python-fastapi-skel`),
also load:

4. The skeleton-specific LLM file: `_skels/<name>/JUNIE-RULES.md`
5. The skeleton documentation page in `_docs/` (for example
   `_docs/python-fastapi-skel.md`)

You must refresh these files whenever the user mentions that the
documentation or rules might have changed.

---

## 2. Project Purpose (High Level)

- This repository is a **Makefile-based project generator system**.
- It manages multiple **skeletons** in `_skels/*-skel/`.
- Each skeleton can generate a new project of a particular stack/framework.
- The main `Makefile` delegates to skeleton Makefiles.
- `_bin/skel-gen` is a relocatable helper to run generators from anywhere.

Your job is to:

1. Maintain the generators and skeletons.
2. Keep dependency versions healthy and reasonably up to date.
3. Preserve developer workflows described in `_docs/`.

Never treat `_test_projects/` as hand-edited source — it is generated output
used for e2e testing.

---

## 3. Directory and Responsibility Overview

- `Makefile` (root)
  - Entry point for all generator tasks.
  - Provides `gen-*` and `test-*` targets.

- `_skels/*-skel/`
  - One directory per skeleton (e.g. `python-fastapi-skel`).
  - Each skeleton must provide at least:
    - `Makefile` – skeleton-level `gen` and `test` targets.
    - `gen` – executable script invoked by the root generator.
    - `merge` – executable script copying overlay files into target projects.
    - `test` – end-to-end test script used by `make test-<name>`.
    - `deps` – system dependency installer.
    - `install-deps` – project dependency installer copied into generated projects.
  - Each skeleton **should** also provide a `JUNIE-RULES.md` file with
    skeleton-specific guidance (see below).

- `_docs/`
  - Primary documentation hub.
  - Contains `LLM-MAINTENANCE.md` (deep LLM guidance) and per-skeleton docs.

- `_test_projects/`
  - Auto-generated test applications used by CI and local `make test-*`.
  - **Never** modify these directly; instead, change the relevant skeleton
    and re-run tests.

---

## 4. LLM Rules Model

### 4.1 Global vs Per-Skeleton Rules

- **Global rules** (this file + `LLM-MAINTENANCE.md`) apply to the whole
  project.
- **Per-skeleton rules** live in `_skels/<name>/JUNIE-RULES.md` and:
  - Describe stack-specific constraints and conventions.
  - Describe how to evolve dependencies and frameworks for that skeleton.
  - Must never contradict global rules; if there is a conflict, global rules
    win unless the user explicitly overrides them.

When maintaining a skeleton, always combine:

1. This file (`_docs/JUNIE-RULES.md`)
2. `_docs/LLM-MAINTENANCE.md`
3. The skeleton-specific `JUNIE-RULES.md`
4. The skeleton documentation in `_docs/`

### 4.2 Updating Rules

When you make significant architectural or workflow changes, you must:

1. Update `_docs/LLM-MAINTENANCE.md` if LLM maintenance procedures change.
2. Update `_docs/JUNIE-RULES.md` if core project-level rules change.
3. Update the relevant `_skels/<name>/JUNIE-RULES.md` for skeleton-specific
   changes.

Never leave behaviour changes undocumented: future LLMs rely on these files.

---

## 5. Safety and Scope Constraints

1. Do **not** change `SKEL_DIR` detection patterns unless the user
   explicitly asks for it; they are subtle and already documented in
   `LLM-MAINTENANCE.md`.
2. Do **not** commit or modify `node_modules/`, `.venv/`, `target/`,
   `dist/` or similar build artefacts.
3. Do **not** edit anything under `_test_projects/` by hand.
4. Prefer small, focused changes over large refactors unless explicitly
   requested by the user.
5. When in doubt about an operation that might be destructive or
   backward-incompatible, ask the user for confirmation.

---

## 6. Version and Dependency Management (Global)

Use `_docs/DEPENDENCIES.md` as the main reference for dependency policies.

- Keep each skeleton on **supported** and **reasonably current** versions of
  its main frameworks and runtime.
- When considering major upgrades (e.g. FastAPI, Django, Spring, Rust
  toolchains) you must:
  1. Check release notes for breaking changes.
  2. Update skeleton code and scripts accordingly.
  3. Run `make clean-test && make test-generators`.

Global version constraints or preferences belong in `_docs/DEPENDENCIES.md`
and/or here; skeleton-specific version rules go into each skeleton's
`JUNIE-RULES.md`.

---

## 7. How Junie Should Work Day-to-Day

### 7.1 General Behaviour

When the user asks you to modify or extend this repository:

1. Identify whether the task is **global** (root Makefile, tooling,
   documentation) or **skeleton-specific**.
2. Load all relevant rules files (this file + per-skeleton `JUNIE-RULES.md`).
3. Follow existing patterns in the affected skeleton or scripts.
4. Update tests and documentation as needed.
5. Prefer incremental improvements that keep all generators passing.

### 7.2 Definition of "Maintenance" for This Project

For this repository, a **maintenance task** has a specific, ordered
workflow. Unless the user explicitly asks for a different flow, treat
"do maintenance" as meaning:

1. **Run tests for generators first**
   - From the project root, run:
     - `make clean-test`
     - `make test-generators`
   - By default this exercises **all** skeletons. If the user has selected
     a single skeleton (for example `python-fastapi-skel`), you may instead
     run the focused targets for that skeleton as documented in
     `_docs/LLM-MAINTENANCE.md`.

2. **Fix all failures before changing rules/docs**
   - Investigate any failing generator or skeleton tests.
   - Apply the minimal changes needed in the relevant skeletons, scripts,
     or configs until **no test failures remain**.
   - Re-run the same tests after each substantive fix to confirm they are
     green.

3. **Then update LLM rules and documentation**
   - After generators and tests are green, review and, if needed, update:
     - `_docs/JUNIE-RULES.md` (global rules),
     - `_docs/LLM-MAINTENANCE.md` (maintenance workflow), and
     - any relevant `_skels/<name>/JUNIE-RULES.md` and skeleton docs
       under `_docs/`.
   - Ensure that any behavioural or workflow changes introduced while
     fixing tests are clearly reflected in these files.

4. **Scope: all skeletons vs. one skeleton**
   - If the user says "maintain the whole project", assume you should run
     tests for **all skeletons** (global `make clean-test && make
     test-generators`) and then adjust global + per-skeleton rules/docs as
     needed.
   - If the user requests maintenance for **one specific skeleton**, you
     may:
     - Run only that skeleton's generator tests and local tests (as
       described in `_docs/LLM-MAINTENANCE.md` and the skeleton's
       `JUNIE-RULES.md`), and
     - Limit rules/doc updates to that skeleton plus any global rules that
       are directly impacted.

This ordering (tests first → fixes until green → rules/docs updates) is the
default maintenance scenario for this repository.
