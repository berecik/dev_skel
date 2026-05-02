# Claude Code Rules — `java-spring-ddd-skel`

Claude-specific complement to `_skels/java-spring-ddd-skel/AGENTS.md` and
`_skels/java-spring-ddd-skel/JUNIE-RULES.md`. Read those first.


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

## 1. Read These Files First (in order)

1. `_skels/java-spring-ddd-skel/CLAUDE.md` (this file)
2. `_skels/java-spring-ddd-skel/AGENTS.md`
3. `_skels/java-spring-ddd-skel/JUNIE-RULES.md`
4. `_docs/java-spring-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- Spring Boot Java backend (production-grade JVM service).
- Generated services live under `<wrapper>/<service_slug>/` (or
  `<wrapper>/service/` when no service name is given).
- Requires JDK 21+ and Maven (`./skel-deps java-spring-skel` installs both).
- **ORM: Spring Data JPA + Hibernate.** Migrated to Spring Data JPA +
  Hibernate during the project-wide ORM migration. The original JDBC
  choice ("we intentionally avoid spring-boot-starter-data-jpa") was
  reversed — the JVM service now follows the same pattern as
  go-skel/GORM, rust-*-skel/SeaORM, and next-js-skel/Drizzle. JPA's
  `spring.jpa.hibernate.ddl-auto=update` handles schema bootstrap
  (replacing the deleted `SchemaInitializer`); `@CreationTimestamp` /
  `@UpdateTimestamp` handle datetime fields automatically. Controllers
  go through `JpaRepository<Entity, Long>` — no `JdbcTemplate` /
  `JdbcClient` allowed. SQLite support is provided by the
  `hibernate-community-dialects` artifact (the
  `spring.jpa.properties.hibernate.dialect.community` property points
  Hibernate at `org.hibernate.community.dialect.SQLiteDialect`).
  Postgres + H2 use Hibernate's built-in dialects with no extra
  configuration. The default-account seed (`user` / `admin`) lives in
  `app.marysia.skel.config.DefaultUserSeeder` as an
  `ApplicationRunner` bean.
- **Shared env contract** (CRITICAL): `application.properties` reads its
  database URL from `${SPRING_DATASOURCE_URL:${DATABASE_JDBC_URL:jdbc:h2:mem:testdb}}`
  and JWT material from `${JWT_SECRET}` / `${JWT_ALGORITHM}` / `${JWT_ISSUER}`
  / `${JWT_ACCESS_TTL}` / `${JWT_REFRESH_TTL}`. Those variables come from
  the wrapper-shared `<wrapper>/.env`. The
  `app.marysia.skel.config.JwtProperties` bean (registered via
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
