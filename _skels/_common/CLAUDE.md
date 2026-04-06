# Claude Code Rules (rendered by skel-gen)

This file is the entrypoint Claude Code loads automatically inside the
generated project. It is the Claude-specific complement to the sibling
`AGENTS.md`. Placeholders such as `${skeleton_name}`, `${project_name}`, and
`${service_dir}` are filled in by `skel-gen` after generation.

When `AGENTS.md` and this file disagree, prefer the **most restrictive**
guidance unless the user explicitly overrides it.

---

## 1. Read These Files First (order)

1. `./CLAUDE.md` (this file)
2. `./AGENTS.md` (cross-agent baseline for this service)
3. `./README.md` (service-level notes, if present)
4. `../README.md` (wrapper overview, if present)
5. If you still have the Dev Skel repository available, also read:
   - `/CLAUDE.md` (global Claude rules)
   - `/AGENTS.md` (global cross-agent rules)
   - `_docs/JUNIE-RULES.md`
   - `_docs/LLM-MAINTENANCE.md`
   - `${skeleton_doc}` (skeleton page for `${skeleton_name}`)

Refresh these files whenever rules or docs change, or after rule-affecting
edits.

---

## 2. Project Snapshot

- This service was generated from the `${skeleton_name}` skeleton.
- Service path: `${service_dir}/` inside project `${project_name}`.
- Wrapper-level scripts (`./run`, `./test`, `./build`, `./stop`,
  `./install-deps`) forward into `${service_dir}/`.

Your goals when editing this service typically include:

1. Keep the developer UX smooth (`./gen`, `./test`, `./run`, etc.).
2. Keep core dependencies healthy and current without breaking users.
3. Keep the generated project production-capable yet approachable.

---

## 3. Claude Code Operational Notes

1. **Plan first** for non-trivial changes (multi-file edits, dependency
   bumps, framework upgrades). Confirm scope with the user when in doubt.
2. **Track progress with the Task tools** for anything beyond ~3 steps.
3. Prefer the dedicated tools (`Read`, `Edit`, `Write`, `Glob`, `Grep`)
   over `Bash`. Reach for `Bash` only when running build/test commands or
   inspecting git state.
4. Use the `Explore` subagent for broad codebase research, the `Plan`
   subagent for architectural design.
5. **Confirm before risky actions** — pushing branches, force-pushing,
   `git reset --hard`, deleting generated state, or rewriting dependency
   manifests all require explicit user approval.
6. **Memory hygiene.** Do not save derivable facts (file layout, conventions)
   into auto-memory; only persist genuinely surprising user preferences or
   non-obvious project facts.

---

## 4. Files to Inspect First (adjust paths as needed)

- `./README.md`
- `./Makefile` (service-level)
- Generator scripts: `./gen`, `./merge`, `./test` (if present)
- Dependency installers: `./deps`, `./install-deps` (if present)
- Core code directories (e.g. `app/`, `src/`, `core/`) — update to match
  this service's actual layout

---

## 5. Maintenance & Testing

Default validation after changes:

```bash
make test
```

If the service uses different commands (lint, e2e, etc.), list them in
`AGENTS.md` and follow them here. When you have the Dev Skel repo
available, also run global checks:

```bash
make clean-test
make test-generators
```

---

## 6. Safety and Constraints

1. Avoid removing generator entrypoints (`gen`, `merge`, `test`, `deps`,
   `install-deps`) without strong reason.
2. Avoid hard-coded, machine-specific paths or environment assumptions.
3. Follow existing patterns for logging, configuration, and project layout
   in this service.
4. Regenerate rather than hand-edit generated fixtures or scaffolds.
5. Ask the user before destructive or backward-incompatible changes.
6. Keep `AGENTS.md` and `CLAUDE.md` in sync when you change cross-agent
   rules.

---

## 7. Verification Checklist (adapt as needed)

- [ ] Service tests are green (`make test` or the noted equivalent).
- [ ] Wrapper-level workflows still function (if present).
- [ ] `AGENTS.md` and `CLAUDE.md` agree with the implemented behaviour.
- [ ] Generated artifacts were regenerated rather than hand-edited.
