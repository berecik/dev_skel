# Claude Code Rules — `dev_skel`

This file is the entrypoint Claude Code loads automatically. It is the
Claude-specific complement to `/AGENTS.md`. Everything in `/AGENTS.md`,
`_docs/JUNIE-RULES.md`, and `_docs/LLM-MAINTENANCE.md` still applies — read
them first and follow them. Sections below add behaviour that is specific to
Claude Code (slash commands, the Plan / Task tooling, persistent memory,
etc.).

When `/AGENTS.md` and this file disagree, prefer the **most restrictive**
guidance unless the user explicitly overrides it. When in doubt, ask.

---

## 1. Read These Files First (in order)

1. `/CLAUDE.md` (this file)
2. `/AGENTS.md` (cross-agent baseline)
3. `_docs/JUNIE-RULES.md` (project-authoritative rules)
4. `_docs/LLM-MAINTENANCE.md` (operational workflows)
5. `_docs/README.md` (documentation index)

When working on a specific skeleton (for example `python-fastapi-skel`), also
load:

6. `_skels/<name>/CLAUDE.md` (if present) **or** `_skels/<name>/AGENTS.md`
7. `_skels/<name>/JUNIE-RULES.md`
8. The skeleton page in `_docs/` (e.g. `_docs/python-fastapi-skel.md`)

Refresh these files whenever the user says rules/docs changed or after you
make rule-affecting edits.

---

## 2. Project Snapshot for Claude

- Multi-skeleton, Makefile-driven project generator. Each skeleton lives in
  `_skels/<lang>-<framework>-skel/` and produces a framework-specific service
  inside a wrapper project.
- The relocatable CLI (`_bin/skel-gen`, `install-dev-skel`, `update-dev-skel`,
  `sync-dev-skel`, `skel-list`) is **Python**, sharing logic via
  `_bin/dev_skel_lib.py`. The legacy `_bin/common.sh` is kept only for
  backwards compatibility — do not extend it.
- After generation, `skel-gen` renders the templated `_skels/_common/AGENTS.md`
  (and, when present, the matching `CLAUDE.md`) into the new project so the
  generated tree ships with agent rules wired in.
- `_test_projects/` is the **only** directory where you may create scratch /
  reproduction / debug projects. Never hand-edit anything inside it —
  regenerate with the appropriate `make gen-*` or `_bin/skel-gen` invocation.

---

## 3. Default Maintenance Workflow

Use this workflow whenever the user says "do maintenance" or asks you to
verify the repo. It mirrors `_docs/LLM-MAINTENANCE.md` so Claude does not
need to context-switch:

1. From the repo root, run:
   - `make clean-test`
   - `make test-generators`
2. Investigate every failure and apply minimal, surgical fixes in the
   affected skeletons / scripts. Re-run the same commands until they are
   green.
3. Once tests pass, update the docs and rules files to match the new
   behaviour:
   - Cross-agent: `/AGENTS.md`, `/CLAUDE.md`
   - Global rules: `_docs/JUNIE-RULES.md`, `_docs/LLM-MAINTENANCE.md`
   - Per-skeleton: `_skels/<name>/AGENTS.md`, `_skels/<name>/CLAUDE.md` (if
     present), `_skels/<name>/JUNIE-RULES.md`, and the matching `_docs/<name>.md`
4. If the user explicitly scoped the request to one skeleton, narrow the
   tests and doc updates to that skeleton plus any global rules that must
   change as a side effect.

For long-running maintenance, prefer running `./maintenance` (or the
underlying `make clean-test && make test-generators && ./test`) in the
background and surface only the failures.

---

## 4. Claude Code Operational Notes

These are conventions specific to the way Claude Code interacts with this
repository:

1. **Plan before non-trivial edits.** If a request will touch more than one
   skeleton, change generator UX, or alter dependency policy, draft a Plan
   first and (when appropriate) confirm with the user before executing it.
2. **Track multi-step work with the Task tools.** Anything with more than
   ~3 distinct steps belongs in a task list so the user can follow progress.
   Mark tasks `in_progress` before starting and `completed` immediately after
   finishing — never batch.
3. **Prefer the dedicated tools** (`Read`, `Edit`, `Write`, `Glob`, `Grep`)
   over shelling out via `Bash`. Reach for `Bash` only when no built-in tool
   fits (running `make`, executing scripts, inspecting git state).
4. **Use the Explore subagent** for broad codebase research that would
   otherwise spam the main context. Use `Plan` for design work. Use
   `general-purpose` agents for parallelisable independent investigations.
5. **Confirm before risky actions.** Pushing branches, force-pushing,
   running `git reset --hard`, deleting `_test_projects/` outside of
   `make clean-test`, or modifying `.dev_skel.conf` all require explicit
   user approval.
6. **Memory hygiene.** This project's structure, conventions, and file
   layout are derivable from the repo itself — do not save those into the
   auto-memory system. Only persist genuinely surprising user preferences
   or non-obvious project facts.
7. **Status line and outputs.** Keep textual answers terse. Use code blocks
   for commands and `path:line` for code references.

---

## 5. Editing Conventions for Claude

1. Always `Read` a file before editing or rewriting it.
2. Prefer minimal, surgical diffs that solve the immediate issue. Do not
   refactor unrelated code or add speculative abstractions.
3. Do not modify generator-owned files for ts-react-skel
   (`package.json`, `package-lock.json`, `tsconfig.json`,
   `tsconfig.node.json`, `vite.config.ts`) — they are managed by Vite's
   create command.
4. Do not modify Django generator-owned files (`manage.py`, key
   `myproject/*` files) or Rust skeleton-owned files (`Cargo.toml`,
   `src/main.rs`) — see each skeleton's `merge` script for the exact lists.
5. Never weaken or skip failing tests. Investigate root causes instead.
6. Never commit `node_modules/`, `.venv/`, `target/`, `dist/`, or other
   build artefacts.
7. Update both `/AGENTS.md` and `/CLAUDE.md` when you change cross-agent
   rules, so other LLM harnesses stay in sync.

---

## 6. Verification Checklist

Before declaring a task done, verify the relevant subset of:

- [ ] `make test-generators` is green for the affected skeletons.
- [ ] Updated docs / rules accurately reflect the new behaviour.
- [ ] `_test_projects/` contents were regenerated (not hand-edited).
- [ ] No build artefacts staged for commit.
- [ ] Cross-agent rule files (`/AGENTS.md`, `/CLAUDE.md`,
      `_docs/JUNIE-RULES.md`) agree with each other.
- [ ] Any new or renamed Python helpers in `_bin/dev_skel_lib.py` are
      consumed correctly by the CLIs that depend on them.
