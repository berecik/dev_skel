# Agents Rules for `js-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`js-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a minimal JavaScript application skeleton (Node.js + browser
  tooling as described in the docs).
- Lives at `_skels/js-skel/`.
- Generates a simple JS project for demos and small apps.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Node.js and core JS tooling reasonably up to date.
3. Ensure generated projects are easy to understand and extend.

---

## 2. Files to Check First

When working on `js-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/js-skel.md` (if present).
2. Skeleton Makefile: `_skels/js-skel/Makefile`.
3. Generator scripts:
   - `_skels/js-skel/gen`
   - `_skels/js-skel/merge`
   - `_skels/js-skel/test_skel`
4. Dependency installers:
   - `_skels/js-skel/deps`
   - `_skels/js-skel/install-deps`
5. Core source (typically under `_skels/js-skel/src/`).

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Node.js and JS Tooling)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the current calendar date (provided by the system) to reason about
   which Node.js LTS and package versions are "current".
2. Prefer a current Node.js LTS release supported by the main tools
   used here.
3. For npm dependencies (see `package.json` / installer scripts):
   - Prefer stable, widely used releases.
   - Avoid experimental or very new major versions unless explicitly
     requested.
4. You must not fabricate specific version numbers. If you cannot reliably
   obtain the latest versions (e.g. no network access), keep existing
   versions and note in commit messages that versions were not updated due to
   unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

---

## 4. Architecture and Style Constraints

1. Keep the skeleton minimal and framework-agnostic where reasonable.
2. Follow existing project layout and naming conventions in `src/` and
   related files.
3. Avoid introducing heavy frameworks unless the documentation for this
   skeleton is updated accordingly.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

If there is a skeleton-specific test command (for example via
`_skels/js-skel/test_skel`), ensure it is covered by the generator tests or
invoke it explicitly when appropriate.

Generated JS test projects under `_test_projects/` (if any for this
generator) should build and run their tests successfully.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do not hard-code machine-specific paths or environment assumptions.
3. Do not introduce breaking dependency upgrades without verifying the
   generator tests.
