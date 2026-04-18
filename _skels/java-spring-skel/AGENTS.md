# Agents Rules for `java-spring-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`java-spring-skel` skeleton.

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

- Provides a Spring-based Java backend skeleton (see `pom.xml` and
  documentation for exact stack).
- Lives at `_skels/java-spring-skel/`.
- Generates a small Spring application for demos and services.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`, `./run-dev`,
   etc.).
2. Keep Java, Spring Boot (or the chosen Spring stack), and test libraries
   reasonably up to date.
3. Ensure generated projects are idiomatic for Spring and easy to extend.

---

## 2. Files to Check First

When working on `java-spring-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/java-spring-skel.md` (if present).
2. Skeleton Makefile: `_skels/java-spring-skel/Makefile`.
3. Generator scripts:
   - `_skels/java-spring-skel/gen`
   - `_skels/java-spring-skel/merge`
   - `_skels/java-spring-skel/test_skel`
4. Dependency installers:
   - `_skels/java-spring-skel/deps`
   - `_skels/java-spring-skel/install-deps`
5. Maven project files and source:
   - `_skels/java-spring-skel/pom.xml`
   - `src/main/java/...`
   - `src/test/java/...`

Do not edit `_test_projects/*` directly; they are generated output.

---

## 3. Version Management Rules (Java and Spring)

Whenever you touch this skeleton, consider whether dependency versions should
be updated.

1. Use the current calendar date to reason about which Java LTS and
   Spring Boot (or Spring stack) versions are "current".
2. Prefer a supported Java LTS release that is recommended for the Spring
   version used by this skeleton.
3. For dependencies in `pom.xml`:
   - Prefer stable, supported Spring and library versions.
   - Review release notes before upgrading major versions of Spring Boot or
     key dependencies (e.g. database drivers, test frameworks).
4. Do not fabricate version numbers. If you cannot confirm current
   versions, keep existing versions and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

If available, also run the skeleton-specific Maven tests for a generated
project.

---

## 4. Architecture and Style Constraints

1. Follow idiomatic Spring Boot (or Spring) project structure, using
   controllers, services, and configuration as already established.
2. Keep demo endpoints minimal but realistic, mirroring existing patterns in
   the example controller and tests.
3. Avoid introducing non-standard patterns or heavy frameworks without
   updating documentation and tests.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run at
least:

```bash
make clean-test
make test-generators
```

Generated Spring test projects under `_test_projects/` should:

1. Build successfully with Maven.
2. Run their tests successfully using the generated `./test` script.

If these expectations cannot be met, document the reason in the relevant
docs file for this skeleton.

---

## 6. Do Not

1. Do not remove or drastically alter the generator entry points
   (`gen`, `merge`, `test`, `deps`, `install-deps`) without strong reason.
2. Do not hard-code environment-specific paths or assumptions beyond
   what the `deps` script guarantees.
3. Do not upgrade Java or Spring in a way that breaks generator tests
   without addressing resulting issues.
