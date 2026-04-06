# Common Agents Rules Template (rendered by skel-gen)

This file is automatically templated by `skel-gen` after your service is
generated. Placeholders such as `${skeleton_name}`, `${project_name}`, and
`${service_dir}` will be filled using your generator inputs. Update the
remaining sections to match the service you just created.

---

## 1. Read These Files First (order)

1. `./AGENTS.md` (this file)
2. `./README.md` (service-level notes, if present)
3. `../README.md` (wrapper overview, if present)
4. If you still have the Dev Skel repository available, also read:
   - `/AGENTS.md` (global rules)
   - `_docs/JUNIE-RULES.md`
   - `_docs/LLM-MAINTENANCE.md`
   - `${skeleton_doc}` (skeleton page for `${skeleton_name}`)

Refresh these whenever docs or rules change, or after rule-affecting edits.

---

## 2. Service Purpose (fill in specifics)

- Describe what `${skeleton_name}` provides for this service.
- Service path: `${service_dir}/` inside project `${project_name}`.
- Mention any generated demo/test fixtures (do not hand-edit regenerated files).

Your goals when editing this service typically include:

1. Keep developer UX smooth (`./gen`, `./test`, `./run`, etc.).
2. Keep core dependencies healthy and current without breaking users.
3. Ensure the generated project stays production-capable yet approachable.

---

## 3. Files to Inspect First (adjust paths as needed)

- `./README.md`
- `./Makefile` (service-level)
- Generator scripts: `./gen`, `./merge`, `./test` (if present)
- Dependency installers: `./deps`, `./install-deps` (if present)
- Core code directories (e.g. `app/`, `src/`, `core/`) — update to match this service

---

## 4. Maintenance & Testing (customize commands)

Document the default way to validate this service after changes:

```bash
make test
```

If the service uses different commands (lint, e2e, etc.), list them here.
When you have the Dev Skel repo available, also run global checks:

```bash
make clean-test
make test-generators
```

---

## 5. Safety and Constraints (keep consistent)

1. Avoid removing generator entrypoints (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Avoid hard-coded, machine-specific paths or assumptions.
3. Follow existing patterns for logging, configuration, and project layout in this service.
4. Regenerate rather than hand-edit generated fixtures or scaffolds.
5. Ask the user before destructive or backward-incompatible changes.

---

## 6. Customization Checklist (update before using)

- Replace any remaining placeholders or TODOs with service-specific details.
- Adjust the “Files to Inspect First” list to match this service’s layout.
- Add dependency/version policies unique to this stack.
- Add architecture/style constraints specific to the framework.
- Add or update service-specific test commands.

---

## 7. Verification Checklist (adapt as needed)

- Service tests are green (`make test` or the noted equivalent).
- Wrapper-level workflows still function (if present).
- Docs/rules reflect any behaviour or dependency changes.
- Generated artifacts were regenerated rather than hand-edited.
