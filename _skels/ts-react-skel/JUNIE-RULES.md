# Junie Rules for `ts-react-skel`

Specialised rules for Junie (and other LLM assistants) when working on the
`ts-react-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a TypeScript + React frontend skeleton (Vite-based, as described
  in the docs and generator scripts).
- Lives at `_skels/ts-react-skel/`.
- Generates a modern React/TS app used for demos and small frontends.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `npm run dev`,
   etc.).
2. Keep Node.js, React, TypeScript, Vite, and testing libraries reasonably
   up to date.
3. Ensure generated projects are easy to bootstrap and extend.

---

## 2. Files to Check First

When working on `ts-react-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/ts-react-skel.md` (if present).
2. Skeleton Makefile: `_skels/ts-react-skel/Makefile`.
3. Generator scripts:
   - `_skels/ts-react-skel/gen`
   - `_skels/ts-react-skel/merge`
   - `_skels/ts-react-skel/test_skel`
4. Dependency installers:
   - `_skels/ts-react-skel/deps`
   - `_skels/ts-react-skel/install-deps`
5. Core source tree under `_skels/ts-react-skel/src/`.

Do **not** edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Node.js, React, TypeScript, Vite)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the **current calendar date** to reason about which Node.js LTS,
   React, TypeScript, and Vite versions are "current".
2. Prefer a current **Node.js LTS** release supported by the toolchain used
   by this skeleton.
3. For npm dependencies (see `package.json` / installer scripts):
   - Prefer stable, widely used releases for React, React DOM, TypeScript,
     Vite, testing libraries, and related tooling.
   - Avoid experimental or very new major versions unless explicitly
     requested.
4. Do **not** fabricate version numbers. If you cannot check current
   versions, keep existing pins and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

---

## 4. Architecture and Style Constraints

1. Keep the project structure aligned with the Vite + React + TypeScript
   layout established by the generator.
2. Follow existing patterns in `src/App.tsx`, tests, and utility modules.
3. Avoid adding framework-specific complexity (state managers, routing
   libraries, etc.) unless documentation is updated and tests are adjusted.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

Ensure that generated React/TS projects can:

1. Install dependencies via the generated `install-deps` script.
2. Run their tests successfully (e.g. via `npm test` or equivalent
   commands).
3. Start the dev server using the documented command (typically
   `npm run dev`).

---

## 6. Do Not

1. Do **not** overwrite generator-owned files excluded by the `merge`
   script (such as `package.json`, `package-lock.json`, `tsconfig*.json`,
   `vite.config.ts`) unless you fully understand the implications.
2. Do **not** change the project layout in ways that break the
   `merge`/`gen` contracts.
3. Do **not** upgrade major library versions without running generator tests
   and verifying that generated apps still build and test.
