# Agents Rules for `next-js-ddd-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`next-js-ddd-skel` skeleton.

Always read these rules after the global `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
and `_docs/LLM-MAINTENANCE.md` files.


## Mandatory Test Artifact Location

- **Mandatory:** Any testing projects, services, data, or files must be created only under `_test_projects/` (the dedicated directory for generated testing skeletons and related test artifacts).

---

## Maintenance Scenario ("let do maintenance" / "let do test-fix loop")

Use this shared scenario whenever the user asks for maintenance (for example: `let do maintenance` or `let do test-fix loop`).

- **1) Finish the requested implementation scenario first.**
- **2) Run tests for changed scope first**, then run full relevant test suites.
- **3) Test code safety** (security/safety checks relevant to the stack and changed paths).
- **4) Simplify and clean up code** (remove dead code, reduce complexity, keep style consistent).
- **5) Run all relevant tests again** after cleanup.
- **6) Fix every issue found** (tests, lint, safety, build, runtime).
- **7) Repeat steps 2–6 until no issues remain.**
- **8) Only then update and synchronize documentation/rules** (`README`, `_docs/`, skeleton docs, agent instructions) to match final behaviour.

This is the default maintenance/test-fix loop and should be commonly understood across all agent entrypoints.

---

## 1. Purpose of This Skeleton

- Provides a minimal JavaScript application skeleton (Node.js + browser
  tooling as described in the docs).
- Lives at `_skels/next-js-ddd-skel/`.
- Generates a simple JS project for demos and small apps.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Node.js and core JS tooling reasonably up to date.
3. Ensure generated projects are easy to understand and extend.

---

## 2. Files to Check First

When working on `next-js-ddd-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/next-js-skel.md` (if present).
2. Skeleton Makefile: `_skels/next-js-ddd-skel/Makefile`.
3. Generator scripts:
   - `_skels/next-js-ddd-skel/gen`
   - `_skels/next-js-ddd-skel/merge`
   - `_skels/next-js-ddd-skel/test_skel`
4. Dependency installers:
   - `_skels/next-js-ddd-skel/deps`
   - `_skels/next-js-ddd-skel/install-deps`
5. Core source (typically under `_skels/next-js-ddd-skel/src/`).

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
`_skels/next-js-ddd-skel/test_skel`), ensure it is covered by the generator tests or
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

---

## DDD Layer Rules (this skeleton uses the FastAPI shape)

This is a DDD-flavored sister skeleton. The HTTP contract is identical
to its flat counterpart, but the source layout follows the canonical
FastAPI shape. Every resource (`items`, `categories`, `orders`,
`catalog`, `state`) is a self-contained module with the same
five-file split:

| File | Role |
| --- | --- |
| `models` (or `dto/`) | DTOs only — request/response shapes |
| `repository` | abstract interface (Get/List/Save/Update/Delete) |
| `adapters/sql` | concrete impl — the only file that touches the ORM/connection |
| `service` | business logic, constructed with a repository (never a DB) |
| `depts` | composition root: builds adapter → service |
| `routes` | HTTP layer: pulls the service, calls one method, never touches the DB |

Cross-resource modules:

- `auth/` — flat (not CRUD); depends on `users.UserRepository`.
- `users/` — repo-only; no service, no public routes. Consumed by
  `auth/` and `seed/` only.
- `shared/` — `errors` (DomainError sentinels), `httpx`
  (jsonError + wrapResponse), `repository` (abstract Repository<T,ID>
  + AbstractUnitOfWork).

When editing this skeleton:

1. **Stay in the resource module.** Adding a new endpoint to `items`?
   Edit `items/{models,service,depts,routes,adapters/sql}`. Don't
   reach into another resource's adapter.
2. **Services take repositories, never DB connections.** New
   collaborator? Inject another repository.
3. **Routes never touch the DB.** They call services. The DB import in
   a routes file is a smell.
4. **DTOs are explicit.** Don't return ORM entities from services.
5. **`depts` is the only place that wires the stack.** `main` (or
   the App Router `route` files, or `Application.java`) imports
   `depts`, never adapters.
6. **Domain errors flow through `shared.DomainError`.** Throw the
   sentinel; let the HTTP layer translate to status codes.

Full reference: [`_docs/DDD-SKELETONS.md`](../../_docs/DDD-SKELETONS.md).
