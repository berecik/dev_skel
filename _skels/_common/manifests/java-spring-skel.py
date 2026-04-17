"""AI manifest for the ``java-spring-skel`` skeleton.

The Spring Boot skeleton already ships an `Item` JDBC record + repository +
service + REST controller + MockMvc tests. This manifest tells
``_bin/skel-gen-ai`` how to rewrite that `Item`-shaped layer for the
user's `{item_class}` entity while preserving the wrapper-shared
`JwtProperties` bean and the env-driven `application.properties`
placeholders.
"""

SYSTEM_PROMPT = """\
You are a senior Spring Boot engineer regenerating one source file inside
the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The Maven project lives at the root of the service directory
  (`{service_subdir}/`) with a `com.example.skel` base package.
- The on-disk service directory inside the wrapper `{project_name}/` is
  `{service_subdir}/`.
- The reference entity is `Item` (table `items`). The user is replacing
  it with `{item_class}` (snake_case `{item_name}`, plural `{items_plural}`).
- The DB table for the new entity MUST be named `{items_plural}` so it
  collides cleanly with other backends in the same wrapper that use the
  same table name (the dev_skel shared-DB integration test relies on
  this).

Shared environment (CRITICAL — every backend service in the wrapper
relies on the same env vars from `<wrapper>/.env`):
- `${{SPRING_DATASOURCE_URL}}` / `${{DATABASE_JDBC_URL}}` — common
  database. Already wired in `application.properties`. Do NOT touch
  application.properties from these prompts.
- `${{JWT_SECRET}}` / `${{JWT_ALGORITHM}}` / `${{JWT_ISSUER}}` /
  `${{JWT_ACCESS_TTL}}` / `${{JWT_REFRESH_TTL}}` — exposed via the
  `com.example.skel.config.JwtProperties` `@ConfigurationProperties`
  bean (registered via `@ConfigurationPropertiesScan` on
  `Application`). Inject the bean wherever you need the secret —
  NEVER hardcode it.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Use Spring Boot 3.x with plain JDBC (`JdbcTemplate` / `JdbcClient`).
  Do NOT use JPA entities or annotations (`@Entity`, `@Table`,
  `@Column`, `@PrePersist`, `@PreUpdate`) — the skeleton uses Java
  records, NOT JPA classes. The model layer is a plain `record` class
  (immutable value object) with a static `MAPPER` `RowMapper<>`.
- Do NOT introduce new dependencies — the pom.xml already has everything
  you need (`spring-boot-starter-web`, `spring-boot-starter-jdbc`,
  `spring-boot-starter-validation`, `spring-boot-starter-actuator`).
- Use `org.springframework.web.bind.annotation.*` for the REST layer.
  Do NOT use `jakarta.persistence.*` — there is no JPA in this project.
- Match the indentation, brace style, and import order of the REFERENCE
  template exactly. Replace every `Item` / `item` / `items` token with
  `{item_class}` / `{item_name}` / `{items_plural}`.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `mvn -q package -DskipTests` after generation to confirm the new "
        "{item_class} layer compiles. The wrapper-shared `<wrapper>/.env` is "
        "already wired in via `application.properties` placeholders."
    ),
    "targets": [
        {
            "path": "src/main/java/com/example/skel/model/{item_class}.java",
            "template": "src/main/java/com/example/skel/model/Item.java",
            "language": "java",
            "description": "model/{item_class}.java — JDBC record (table `{items_plural}`)",
            "prompt": """\
Rewrite `model/Item.java` as `model/{item_class}.java` for the
`{items_plural}` table.

Required transformations:
- Class name: `{item_class}`.
- `@Table(name = "{items_plural}")`.
- Keep the `id`, `name`, `description`, `createdAt`, `updatedAt` fields
  exactly as the REFERENCE has them (this matches the canonical
  `<items_plural>` schema used by `_bin/skel-test-shared-db`).
- Add an `is_completed` boolean column (`@Column(name =
  "is_completed", nullable = false) private boolean isCompleted =
  false;`) and the matching getter/setter.
- Keep the `@PrePersist` / `@PreUpdate` lifecycle callbacks unchanged.
- Constructor signature: a no-arg constructor + a `(String name, String
  description)` convenience constructor (mirror the REFERENCE).

Imports: only `jakarta.persistence.*`,
`jakarta.validation.constraints.NotBlank`,
`jakarta.validation.constraints.Size`, `java.time.LocalDateTime`.

REFERENCE (`model/Item.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/com/example/skel/repository/{item_class}Repository.java",
            "template": "src/main/java/com/example/skel/repository/ItemRepository.java",
            "language": "java",
            "description": "repository/{item_class}Repository.java — JDBC repository",
            "prompt": """\
Rewrite `repository/ItemRepository.java` as
`repository/{item_class}Repository.java`.

Required transformations:
- Interface name: `{item_class}Repository`.
- Extends `JpaRepository<{item_class}, Long>`.
- Keep the `findByNameContainingIgnoreCase(String name)` finder
  signature unchanged but with `{item_class}` as the return type.
- Imports: `com.example.skel.model.{item_class}`,
  `org.springframework.data.jpa.repository.JpaRepository`,
  `org.springframework.stereotype.Repository`, `java.util.List`.
- Match the REFERENCE indentation/blank-line style exactly.

REFERENCE (`repository/ItemRepository.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/com/example/skel/service/{item_class}Service.java",
            "template": "src/main/java/com/example/skel/service/ItemService.java",
            "language": "java",
            "description": "service/{item_class}Service.java — transactional service layer",
            "prompt": """\
Rewrite `service/ItemService.java` as `service/{item_class}Service.java`.

Required transformations:
- Class name: `{item_class}Service`.
- Constructor takes `{item_class}Repository`.
- All `Item` references become `{item_class}`.
- Keep `findAll`, `findById`, `save`, `deleteById`, and `searchByName`
  exactly as the REFERENCE.
- Imports: `com.example.skel.model.{item_class}`,
  `com.example.skel.repository.{item_class}Repository`,
  `org.springframework.stereotype.Service`,
  `org.springframework.transaction.annotation.Transactional`,
  `java.util.List`, `java.util.Optional`.

REFERENCE (`service/ItemService.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/com/example/skel/controller/{item_class}Controller.java",
            "template": "src/main/java/com/example/skel/controller/ItemController.java",
            "language": "java",
            "description": "controller/{item_class}Controller.java — REST controller",
            "prompt": """\
Rewrite `controller/ItemController.java` as
`controller/{item_class}Controller.java` for the `{item_class}` entity.

Required transformations:
- Class name: `{item_class}Controller`.
- `@RequestMapping("/api/{items_plural}")`.
- All `Item` / `itemService` references become `{item_class}` /
  `{item_name}Service`.
- Keep the GET-list, GET-by-id, POST-create, PUT-update, DELETE, and
  GET /search endpoints exactly as the REFERENCE wires them.

Authentication style for this service: `{auth_type}`.
- When `{auth_type}` is `none`: leave the controller as-is (no auth
  annotations).
- For any other `{auth_type}`: add a constructor parameter
  `JwtProperties jwtProperties` and store it in a final field. Add a
  one-line comment above each mutating endpoint
  (`POST` / `PUT` / `DELETE`) noting that token verification against
  `jwtProperties.getSecret()` belongs in a Spring Security
  `OncePerRequestFilter` — wiring that filter is left to the user, but
  the secret MUST come from `jwtProperties.getSecret()`, never a
  hardcoded constant. Add the import
  `import com.example.skel.config.JwtProperties;` to the imports list.

Imports beyond the REFERENCE: only `JwtProperties` when `{auth_type}` is
not `none`.

REFERENCE (`controller/ItemController.java`):
---
{template}
---
""",
        },
        {
            "path": "src/test/java/com/example/skel/controller/{item_class}ControllerTest.java",
            "template": "src/test/java/com/example/skel/controller/ItemControllerTest.java",
            "language": "java",
            "description": "test/controller/{item_class}ControllerTest.java — MockMvc tests",
            "prompt": """\
Rewrite `test/controller/ItemControllerTest.java` as
`test/controller/{item_class}ControllerTest.java` for the
`{item_class}` entity.

Required transformations:
- Class name: `{item_class}ControllerTest`.
- `@MockBean private {item_class}Service {item_name}Service;`.
- All `Item` references become `{item_class}`; URLs use
  `/api/{items_plural}`.
- Keep the four reference tests:
  - `getAll{item_class}s_ReturnsList`
  - `get{item_class}ById_WhenExists_Returns{item_class}`
  - `get{item_class}ById_WhenNotExists_ReturnsNotFound`
  - `create{item_class}_ReturnsCreated{item_class}`
- Use `new {item_class}("Test {item_class}", "Description")` for
  fixtures.
- Imports: `com.example.skel.model.{item_class}`,
  `com.example.skel.service.{item_class}Service`, plus the existing
  Spring Boot test + Mockito + Jackson imports from the REFERENCE.

REFERENCE (`test/controller/ItemControllerTest.java`):
---
{template}
---
""",
        },
    ],
}


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Spring Boot 3 engineer integrating a freshly generated
service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`java-spring-skel`). It already ships:
- The wrapper-shared `Item` model + `ItemController` mounted at `/api/items`
  using JDBC (`JdbcTemplate` / `JdbcClient`, NOT JPA).
- The wrapper-shared `ReactState` model + handlers mounted at `/api/state`
  and `/api/state/{{key}}`.
- A user-chosen `{item_class}` model + controller (the per-target manifest
  rewrote `Item` to `{item_class}` for this run).
- JWT auth via the `JwtProperties` bean (`@ConfigurationProperties`) +
  `JwtAuthInterceptor` — the secret comes from `jwtProperties.getSecret()`
  (the wrapper-shared secret — NEVER hardcode it).
- The wrapper-shared `<wrapper>/.env` is loaded by `application.properties`
  placeholders so `SPRING_DATASOURCE_URL` / `DATABASE_JDBC_URL` and the JWT
  vars are identical to every other backend in the project.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Java client for each sibling backend the new service
   should call. The client must read the sibling's URL from
   `System.getenv("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. JUnit 5 integration tests that exercise the cross-service flows
   end-to-end via the wrapper-shared SQLite database (and, when
   sibling backends are present, via the typed clients above).

Coding rules:
- Use **Spring Boot 3.x** with JDBC (`JdbcTemplate` / `JdbcClient`).
  Do NOT use Spring Data JPA in the integration layer. Do NOT
  introduce new dependencies beyond what the pom.xml already pins.
- Use `RestTemplate` or `java.net.HttpURLConnection` for sibling
  HTTP calls. Do NOT add `spring-boot-starter-webflux`, `okhttp`,
  or any other HTTP client library.
- Read JWT material via the `JwtProperties` bean —
  `jwtProperties.getSecret()`. NEVER hardcode the secret.
- Use JUnit 5 (`@Test`, `@BeforeAll`, `Assertions.*`) for tests.
  Guard sibling calls with `try/catch` + `Assumptions.assumeTrue()`
  so tests skip gracefully when a sibling is unreachable.
- Models: `Item` (with `categoryId`), `Category`, `ReactState`
  records.
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the new service's own `/api/items`, `/api/state`, and
  `/api/{items_plural}` endpoints. Do not assume sibling services
  exist; gracefully degrade.

User-supplied integration instructions (free-form, take with the same
weight as the rules above):
{integration_extra}

User-supplied backend instructions (already applied during the
per-target phase, repeated here so the integration code stays
consistent):
{backend_extra}
"""


INTEGRATION_MANIFEST = {
    "system_prompt": INTEGRATION_SYSTEM_PROMPT,
    "notes": (
        "Integration phase: writes src/main/java/.../integration/SiblingClients.java "
        "and src/test/java/.../integration/IntegrationTest.java, then runs the "
        "test-and-fix loop via `./test`."
    ),
    "test_command": "./test",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "src/main/java/com/example/skel/integration/SiblingClients.java",
            "language": "java",
            "description": "integration/SiblingClients.java — typed HTTP clients for sibling backends",
            "prompt": """\
Write `src/main/java/com/example/skel/integration/SiblingClients.java`.
The class exposes one typed inner client class per sibling backend in the
wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Package: `com.example.skel.integration`.
- Use `java.net.HttpURLConnection` or `org.springframework.web.client.RestTemplate`
  for HTTP calls. Do NOT add external HTTP client dependencies.
- Each sibling backend gets a static inner class named
  `<PascalSlug>Client`. The class:
    - Reads its base URL from `System.getenv("SERVICE_URL_<UPPER_SLUG>")`
      in the constructor. Throws `IllegalStateException` with a clear
      message when the env var is missing.
    - Accepts an optional `String token` parameter; when non-null,
      every request sends `Authorization: Bearer <token>`.
    - Exposes `listItems()` and `getState(String key)` methods that
      hit the sibling's wrapper-shared `/api/items` and
      `/api/state/<key>` endpoints. Return parsed JSON as
      `java.util.List<java.util.Map<String, Object>>` or
      `java.util.Map<String, Object>` respectively.
    - Throws `IntegrationException` (defined at the top of the file)
      on non-2xx responses, with the status code and response body.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define the `IntegrationException` class and an empty
  `SiblingClients` wrapper with no inner classes. Do NOT define dummy
  client classes for non-existent siblings.
- Use standard Java conventions: 4-space indentation, PascalCase
  classes, camelCase methods.

Output the full file contents only.
""",
        },
        {
            "path": "src/test/java/com/example/skel/integration/IntegrationTest.java",
            "language": "java",
            "description": "test/integration/IntegrationTest.java — cross-service JUnit 5 cases",
            "prompt": """\
Write `src/test/java/com/example/skel/integration/IntegrationTest.java`.
JUnit 5 integration tests that exercise the new `{service_label}` service
end-to-end and (when sibling backends are present) verify the cross-service
flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use JUnit 5 (`org.junit.jupiter.api.*`) and Spring Boot Test
  (`@SpringBootTest`). Do NOT use JUnit 4 or TestNG.
- Guard sibling client calls with `try/catch` +
  `org.junit.jupiter.api.Assumptions.assumeTrue()` so tests skip
  gracefully when the env var is missing or the sibling is unreachable.
- Use `RestTemplate` for HTTP calls against the local service's
  endpoints during tests.

Required tests:

1. `testItemsEndpointRoundTrip` — use JDBC (`JdbcTemplate`) to insert
   an `Item` row into the `items` table, then query and assert the row
   exists.

2. `testReactStateRoundTrip` — insert a `ReactState` row with
   key="test_key" and a JSON value, read it back, assert the value
   matches.

3. `testItemsPluralEndpointUsesJwt` — construct a JWT token using
   `jwtProperties.getSecret()`, then make an authenticated request to
   `/api/{items_plural}` and assert a 200 response.

4. `testJwtSecretIsWrapperShared` — assert that
   `jwtProperties.getSecret()` equals
   `System.getenv("JWT_SECRET")` (or is non-null when the env var is
   not set).

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `testSibling<PascalSlug>ItemsVisibleViaSharedDb`.
   Guard instantiation like this:
   ```java
   try {{
       var client = new SiblingClients.<PascalSlug>Client();
   }} catch (IllegalStateException e) {{
       Assumptions.assumeTrue(false, "SERVICE_URL_<SLUG> not set");
   }}
   ```
   Then call `client.listItems()` inside `try/catch` and skip if
   unreachable.

6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Imports:
- `org.junit.jupiter.api.*`
- `org.junit.jupiter.api.Assumptions`
- `org.springframework.boot.test.context.SpringBootTest`
- `org.springframework.beans.factory.annotation.Autowired`
- `org.springframework.jdbc.core.JdbcTemplate`
- `com.example.skel.config.JwtProperties`
- (when {sibling_count} > 0) `com.example.skel.integration.SiblingClients`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
