# Claude Code Rules — `java-spring-skel`

Claude-specific complement to `_skels/java-spring-skel/AGENTS.md` and
`_skels/java-spring-skel/JUNIE-RULES.md`. Read those first.

---

## 1. Read These Files First (in order)

1. `_skels/java-spring-skel/CLAUDE.md` (this file)
2. `_skels/java-spring-skel/AGENTS.md`
3. `_skels/java-spring-skel/JUNIE-RULES.md`
4. `_docs/java-spring-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Spring Boot Java backend (production-grade JVM service).
- Generated services live under `<wrapper>/service-1/`,
  `<wrapper>/service-2/`, ...
- Requires JDK 21+ and Maven (`./skel-deps java-spring-skel` installs both).

---

## 3. Claude Operational Notes

1. **Always `Read` before editing** any file under
   `src/main/java/`, `src/test/java/`, or `pom.xml`.
2. **Plan Spring Boot / Java upgrades** and confirm scope with the user
   before editing `pom.xml` or the Maven wrapper. Review release notes for
   breaking changes first.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/java-spring-skel && make test
   ```
4. Never hand-edit `_test_projects/test-spring-app` — regenerate with
   `make gen-spring NAME=_test_projects/<name>`.
5. Keep demo controllers and tests minimal but idiomatic Spring Boot.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (`mvn compile -q` passes).
- [ ] Spring skeleton-specific tests pass.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
