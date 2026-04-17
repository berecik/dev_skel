# SKEL_BACKPORT_COMMAND — internal `dev_skel` RAG-based service-to-template backport

This document is the standalone source of truth for
`_bin/skel-backport`: an internal `dev_skel` command that takes changes
made in a generated service and writes them back into the corresponding
skeleton/template sources.

Unlike `./ai`, which is a generated-service-local command,
`skel-backport` runs from the `dev_skel` repository root and is a
**maintainer workflow**. It is the inverse of generation:

- `skel-gen*`: template → generated service
- `./ai`: generated service → generated service
- `skel-backport`: generated service → skeleton/template source

The command uses `dev_skel`'s internal local RAG stack, local project
context, and Ollama by default. The provider boundary should remain
abstract enough to support a future alternative such as `Exo`.

---

## 1. Why this document exists

The previous merged refactor plan combined Cookiecutter migration and
`skel-backport` into one large document. That coupling made the intent
harder to maintain. From now on:

- `COOKIECUTTER-REFACTOR.md` defines the template substrate.
- `SKEL_BACKPORT_COMMAND.md` defines the service-to-template command.
- `SERVICE_REFACTOR_COMMAND.md` defines the generated-service `./ai`
  workflow.

The backport command depends on the Cookiecutter migration, but it is a
separate feature with its own runtime, safety rules, prompts, and test
matrix.

---

## 2. Product goal

Add `_bin/skel-backport` as an internal `dev_skel` command that:

1. Generates or targets a test service created from a skeleton.
2. Uses local RAG to understand the relationship between the service,
   the skeleton template tree, related docs, and sibling template files.
3. Produces a proposed set of template edits that backport the service's
   changes into the skeleton.
4. Applies those edits only inside the allowed skeleton/template scope.
5. Re-generates and re-tests until the skeleton is green or the command
   stops with a preserved failure artefact.

The command is **internal to `dev_skel`**, not something embedded into
generated end-user projects.

---

## 3. Hard requirements

1. **Internal-only command.** The entrypoint lives under `_bin/` and is
   executed from the `dev_skel` root.
2. **RAG-backed reasoning.** The command reuses the existing
   `_bin/skel_rag/` infrastructure rather than inventing a separate AI
   stack.
3. **Local-first LLM provider.** Default to Ollama; keep provider calls
   behind an adapter boundary.
4. **Template-only writes.** The apply step may write only to the target
   skeleton/template tree and associated maintainer-owned metadata.
5. **Mandatory verification loop.** After apply, regenerate and run the
   relevant tests before accepting the backport.
6. **Reproducible artefacts.** Every run stores prompts, retrieved
   context, proposed files, test output, and final status in a stable
   `.ai`-style artefact directory under the repo.

---

## 4. Target UX

### Core commands

```bash
_bin/skel-backport generate <skel>
_bin/skel-backport propose <generated-service>
_bin/skel-backport apply <generated-service>
```

### Expected flow

1. Maintainer generates a test service from a chosen skeleton.
2. Maintainer edits the generated service manually and/or with
   `./ai`.
3. Maintainer runs `_bin/skel-backport propose <service>` to inspect the
   suggested template edits.
4. Maintainer runs `_bin/skel-backport apply <service>` to write the
   template changes.
5. The command regenerates and runs the relevant tests.
6. If verification fails, the fix-loop either converges or exits with
   artifacts preserved for inspection.

---

## 5. Architecture

### 5.1 Input side

- Generated service tree
- Source skeleton/template tree
- Skeleton-specific docs/rules
- Global maintenance docs
- Existing RAG retrieval context from `_bin/skel_rag/`

### 5.2 Retrieval side

The retrieval layer should prefer:

1. Matching template files for the changed generated files
2. Sibling template files in the same skeleton
3. Shared wrapper/common template files
4. Relevant maintenance docs and skeleton rules

The command should keep retrieval policy in `dev_skel` code, not in an
external host tool.

### 5.3 Output side

The model should emit full-file template replacements or clearly scoped
new template files, plus rationale. The apply layer must reject:

- writes outside the allowed skeleton/template subtree
- duplicate target paths
- absolute paths or `..` escapes
- malformed file blocks or empty bodies

---

## 6. Safety model

- Default to `propose`/dry-run style inspection before apply.
- Before writing, capture repo state so failures can be rolled back.
- Never modify `_test_projects/` by hand; any generated verification
  project must be created through the normal test/generation workflow.
- Preserve unrelated dirty worktree changes.
- Keep the blast radius limited to the chosen skeleton and explicitly
  allowed shared template files.

---

## 7. Verification model

At minimum, each successful apply must:

1. Re-generate a fresh project/service from the edited skeleton.
2. Run the directly relevant skeleton tests.
3. Run broader generator coverage as needed for shared-template changes.
4. Preserve run artifacts when verification fails.

Preferred default verification cadence, per project rules:

```bash
make clean-test
make test-generators
```

When only one skeleton is touched, scoped skeleton-level tests may run
first, but the final accepted change should still respect the repo's
generator coverage expectations.

---

## 8. Relationship to other agent workflows

- `./ai` is the embedded per-service agent workflow for generated
  projects.
- `skel-backport` is the maintainer-side reverse flow that upgrades the
  skeleton/template itself.
- Both should reuse the same internal `dev_skel` RAG substrate and the
  same provider abstraction.
- Optional host integrations such as OpenClaw may sit above these
  workflows, but the source of truth for retrieval policy, safety, file
  application, and verification remains inside `dev_skel`.

---

## 9. Implementation slices

1. Add/solidify the `_bin/skel-backport` CLI entrypoint and subcommands.
2. Reuse `RagAgent`/prompt plumbing for propose/apply flows.
3. Add template-target mapping and path safety validation.
4. Add regeneration + test/fix-loop verification.
5. Add fixtures and fake-LLM tests for malformed-output scenarios.
6. Document maintainer workflow in `_docs/LLM-MAINTENANCE.md`.

---

## 10. Main risks

- Incorrect service-to-template mapping when the template substrate is
  still partly legacy.
- Overwriting shared common files too broadly.
- Coupling prompt logic too tightly to Ollama instead of the provider
  adapter boundary.
- Treating backport as a generated-project feature instead of an
  internal maintainer workflow.

---

## 11. Related documents

- `COOKIECUTTER-REFACTOR.md`
- `SERVICE_REFACTOR_COMMAND.md`
- `_docs/LLM-MAINTENANCE.md`
- `_docs/JUNIE-RULES.md`
