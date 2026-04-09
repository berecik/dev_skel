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
- Generated services live under `<wrapper>/<service_slug>/` (or
  `<wrapper>/service/` when no service name is given).
- Requires JDK 21+ and Maven (`./skel-deps java-spring-skel` installs both).
- **Shared env contract** (CRITICAL): `application.properties` reads its
  database URL from `${SPRING_DATASOURCE_URL:${DATABASE_JDBC_URL:jdbc:h2:mem:testdb}}`
  and JWT material from `${JWT_SECRET}` / `${JWT_ALGORITHM}` / `${JWT_ISSUER}`
  / `${JWT_ACCESS_TTL}` / `${JWT_REFRESH_TTL}`. Those variables come from
  the wrapper-shared `<wrapper>/.env`. The
  `com.example.skel.config.JwtProperties` bean (registered via
  `@ConfigurationPropertiesScan` on `Application`) exposes them as
  `app.jwt.*` for injection. Never put a JWT secret in a Java constant
  or in `application.properties` itself — the env-driven flow is the
  contract that makes a token issued by the JVM service interchangeable
  with one issued by a Python or Rust service in the same wrapper.

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
