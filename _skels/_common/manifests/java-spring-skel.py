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
  (`{service_subdir}/`) with a `app.marysia.skel` base package.
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
  `app.marysia.skel.config.JwtProperties` `@ConfigurationProperties`
  bean (registered via `@ConfigurationPropertiesScan` on
  `Application`). Inject the bean wherever you need the secret —
  NEVER hardcode it.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules (CRITICAL — violating these causes compilation failures):
- Use Spring Boot 3.x with plain JDBC (`JdbcTemplate` / `JdbcClient`).
  Do NOT use JPA entities or annotations (`@Entity`, `@Table`,
  `@Column`, `@Id`, `@GeneratedValue`, `@PrePersist`, `@PreUpdate`)
  — the skeleton uses Java RECORDS, NOT JPA classes. The model layer
  is a plain `record` (immutable value object). The repository is a
  concrete `@Repository` class with a static `MAPPER` `RowMapper<>`.
- Do NOT import `jakarta.persistence.*` — there is NO JPA on the
  classpath (`spring-boot-starter-data-jpa` is NOT in pom.xml).
- Do NOT import `jakarta.validation.constraints.*` — there is NO Bean
  Validation on the classpath (`spring-boot-starter-validation` is NOT
  in pom.xml). Use manual validation in the controller instead.
- Records are IMMUTABLE — do NOT generate setter methods, `@PrePersist`
  / `@PreUpdate` lifecycle callbacks, or builder patterns. Construct
  records via their canonical all-args constructor only.
- Do NOT use `JpaRepository`, `CrudRepository`, or any Spring Data
  interface. The repository is a concrete class that injects
  `JdbcTemplate` and `JdbcClient`.
- Do NOT introduce new dependencies — the pom.xml already has everything
  you need (`spring-boot-starter-web`, `spring-boot-starter-jdbc`,
  `spring-boot-starter-actuator`, `spring-security-crypto`, `jjwt-*`).
- Use `org.springframework.web.bind.annotation.*` for the REST layer.
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
            "path": "src/main/java/app/marysia/skel/model/{item_class}.java",
            "template": "src/main/java/app/marysia/skel/model/Item.java",
            "language": "java",
            "description": "model/{item_class}.java — plain Java record (table `{items_plural}`)",
            "prompt": """\
Rewrite `model/Item.java` as `model/{item_class}.java` for the
`{items_plural}` table.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure):
- This skeleton uses plain Java RECORDS, NOT JPA entity classes.
- Do NOT import jakarta.persistence.* or jakarta.validation.* — there is
  NO JPA and NO Bean Validation on the classpath.
- Do NOT use @Entity, @Table, @Column, @Id, @GeneratedValue, @PrePersist,
  @PreUpdate, @NotBlank, @Size, or ANY JPA/validation annotation.
- Records are IMMUTABLE — do NOT add setter methods, @PrePersist hooks,
  or any mutable lifecycle callbacks.
- Use JdbcTemplate/JdbcClient for all database access (handled by the
  repository, not the model).

Required transformations:
- Record name: `{item_class}`.
- Fields: `Long id`, `String name`, `String description`,
  `boolean isCompleted`, `Long categoryId`, `String createdAt`,
  `String updatedAt` — these match the canonical `{items_plural}`
  schema used by the shared-DB integration test.
- The record has NO annotations and NO additional methods beyond the
  implicit record accessors.
- Package: `app.marysia.skel.model`.

Here is the EXACT pattern you MUST follow (replacing Item with
{item_class}):

```java
package app.marysia.skel.model;

/**
 * Wrapper-shared {{@code {items_plural}}} resource.
 *
 * <p>Jackson serialises the camelCase Java fields to snake_case JSON
 * keys because {{@code spring.jackson.property-naming-strategy=SNAKE_CASE}}
 * is set globally in {{@code application.properties}}.
 */
public record {item_class}(
    Long id,
    String name,
    String description,
    boolean isCompleted,
    Long categoryId,
    String createdAt,
    String updatedAt
) {{
}}
```

Output ONLY the Java source code above (with {item_class} substituted).
No markdown fences, no commentary.

REFERENCE (`model/Item.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/repository/{item_class}Repository.java",
            "template": "src/main/java/app/marysia/skel/repository/ItemRepository.java",
            "language": "java",
            "description": "repository/{item_class}Repository.java — plain JDBC repository (NOT JPA)",
            "prompt": """\
Rewrite `repository/ItemRepository.java` as
`repository/{item_class}Repository.java`.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure):
- This skeleton uses plain Java RECORDS, NOT JPA entity classes.
- Do NOT import jakarta.persistence.* or jakarta.validation.* — there is
  NO JPA on the classpath.
- Do NOT use JpaRepository, CrudRepository, or any Spring Data interface.
- This is a CONCRETE CLASS annotated with @Repository, NOT an interface.
- Use JdbcTemplate and JdbcClient for all database access.
- Records are IMMUTABLE — do NOT call setter methods on them.

Required transformations:
- Class name: `{item_class}Repository`.
- All `Item` references become `{item_class}`.
- Table name in SQL: `{items_plural}`.
- The static `MAPPER` RowMapper builds a `{item_class}` via its record
  constructor.

Here is the EXACT pattern you MUST follow (replacing Item/{item_class}
and items/{items_plural}):

```java
package app.marysia.skel.repository;

import app.marysia.skel.model.{item_class};
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

@Repository
public class {item_class}Repository {{

    private static final DateTimeFormatter ISO =
        DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");

    private static final RowMapper<{item_class}> MAPPER = (rs, _row) -> {{
        long catId = rs.getLong("category_id");
        Long categoryId = rs.wasNull() ? null : catId;
        return new {item_class}(
            rs.getLong("id"),
            rs.getString("name"),
            rs.getString("description"),
            rs.getBoolean("is_completed"),
            categoryId,
            rs.getString("created_at"),
            rs.getString("updated_at")
        );
    }};

    private final JdbcTemplate jdbc;
    private final JdbcClient client;

    public {item_class}Repository(JdbcTemplate jdbc) {{
        this.jdbc = jdbc;
        this.client = JdbcClient.create(jdbc);
    }}

    public List<{item_class}> findAll() {{
        return client
            .sql("SELECT id, name, description, is_completed, category_id, created_at, updated_at "
                + "FROM {items_plural} ORDER BY created_at DESC, id DESC")
            .query(MAPPER)
            .list();
    }}

    public Optional<{item_class}> findById(long id) {{
        try {{
            return Optional.of(
                client
                    .sql("SELECT id, name, description, is_completed, category_id, created_at, updated_at "
                        + "FROM {items_plural} WHERE id = ?")
                    .param(id)
                    .query(MAPPER)
                    .single()
            );
        }} catch (EmptyResultDataAccessException e) {{
            return Optional.empty();
        }}
    }}

    public {item_class} insert(String name, String description, boolean isCompleted, Long categoryId) {{
        String now = nowIso();
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbc.update(connection -> {{
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO {items_plural} (name, description, is_completed, category_id, created_at, updated_at) "
                    + "VALUES (?, ?, ?, ?, ?, ?)",
                new String[]{{"id"}}
            );
            ps.setString(1, name);
            ps.setString(2, description);
            ps.setBoolean(3, isCompleted);
            if (categoryId != null) {{
                ps.setLong(4, categoryId);
            }} else {{
                ps.setNull(4, java.sql.Types.BIGINT);
            }}
            ps.setString(5, now);
            ps.setString(6, now);
            return ps;
        }}, keyHolder);
        Number key = Objects.requireNonNull(keyHolder.getKey(), "INSERT did not return a generated key");
        return new {item_class}(key.longValue(), name, description, isCompleted, categoryId, now, now);
    }}

    public Optional<{item_class}> markCompleted(long id) {{
        String now = nowIso();
        int updated = jdbc.update(
            "UPDATE {items_plural} SET is_completed = ?, updated_at = ? WHERE id = ?",
            true, now, id
        );
        if (updated == 0) {{
            return Optional.empty();
        }}
        return findById(id);
    }}

    private static String nowIso() {{
        return OffsetDateTime.now(ZoneOffset.UTC).format(ISO);
    }}
}}
```

Output the COMPLETE file following the pattern above exactly.
No markdown fences, no commentary.

REFERENCE (`repository/ItemRepository.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/service/{item_class}Service.java",
            "template": "src/main/java/app/marysia/skel/service/ItemService.java",
            "language": "java",
            "description": "service/{item_class}Service.java — service layer delegating to JDBC repository",
            "prompt": """\
Rewrite `service/ItemService.java` as `service/{item_class}Service.java`.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure):
- This skeleton uses plain Java RECORDS, NOT JPA entity classes.
- Do NOT import jakarta.persistence.* or jakarta.validation.*.
- Do NOT use @Transactional — the skeleton does not use JPA transactions.
- The repository is a CONCRETE CLASS (not a Spring Data interface), so
  the service calls `repository.insert(...)` and
  `repository.markCompleted(...)`, NOT `repository.save(...)` or
  `repository.deleteById(...)`.
- Records are IMMUTABLE — do NOT call setter methods on them.

Required transformations:
- Class name: `{item_class}Service`.
- Constructor takes `{item_class}Repository`.
- All `Item` references become `{item_class}`.

Here is the EXACT pattern you MUST follow (replacing Item/{item_class}):

```java
package app.marysia.skel.service;

import app.marysia.skel.model.{item_class};
import app.marysia.skel.repository.{item_class}Repository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class {item_class}Service {{

    private final {item_class}Repository {item_name}s;

    public {item_class}Service({item_class}Repository {item_name}s) {{
        this.{item_name}s = {item_name}s;
    }}

    public List<{item_class}> findAll() {{
        return {item_name}s.findAll();
    }}

    public Optional<{item_class}> findById(long id) {{
        return {item_name}s.findById(id);
    }}

    public {item_class} create(String name, String description, boolean isCompleted, Long categoryId) {{
        return {item_name}s.insert(name, description, isCompleted, categoryId);
    }}

    public Optional<{item_class}> complete(long id) {{
        return {item_name}s.markCompleted(id);
    }}
}}
```

Output the COMPLETE file following the pattern above exactly.
No markdown fences, no commentary.

REFERENCE (`service/ItemService.java`):
---
{template}
---
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/controller/{item_class}Controller.java",
            "template": "src/main/java/app/marysia/skel/controller/ItemController.java",
            "language": "java",
            "description": "controller/{item_class}Controller.java — REST controller using JDBC-backed service",
            "prompt": """\
Rewrite `controller/ItemController.java` as
`controller/{item_class}Controller.java` for the `{item_class}` entity.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure):
- This skeleton uses plain Java RECORDS, NOT JPA entity classes.
- Do NOT import jakarta.persistence.* or jakarta.validation.*.
- Use JdbcTemplate/JdbcClient for all database access (via the service
  and repository layers — the controller does NOT touch JDBC directly).
- Records are IMMUTABLE — do NOT use setter methods or @PrePersist/@PreUpdate.
- The controller uses `AuthUser` from the security package for JWT auth,
  injected via `AuthUserArgumentResolver`. Every handler method accepts
  an `AuthUser user` parameter.
- The controller defines an inner `CreateItemRequest` record for POST
  bodies and an inner `ApiException` class for error responses.

Required transformations:
- Class name: `{item_class}Controller`.
- `@RequestMapping("/api/{items_plural}")`.
- All `Item` / `ItemService` references become `{item_class}` /
  `{item_class}Service`.
- The service field is named `{item_name}s`.
- Keep the GET list, POST create, GET by id, and POST complete endpoints
  exactly as the REFERENCE wires them.

Here is the EXACT pattern you MUST follow (replacing Item/{item_class}
and items/{items_plural}):

```java
package app.marysia.skel.controller;

import app.marysia.skel.model.{item_class};
import app.marysia.skel.security.AuthUser;
import app.marysia.skel.service.{item_class}Service;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/{items_plural}")
public class {item_class}Controller {{

    private final {item_class}Service {item_name}s;

    public {item_class}Controller({item_class}Service {item_name}s) {{
        this.{item_name}s = {item_name}s;
    }}

    @GetMapping
    public List<{item_class}> list(@SuppressWarnings("unused") AuthUser user) {{
        return {item_name}s.findAll();
    }}

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public {item_class} create(@SuppressWarnings("unused") AuthUser user,
                       @RequestBody Create{item_class}Request body) {{
        if (body == null || body.name() == null || body.name().isBlank()) {{
            throw new ApiException(HttpStatus.BAD_REQUEST, "{item_name} name cannot be empty");
        }}
        boolean isCompleted = body.isCompleted() != null && body.isCompleted();
        return {item_name}s.create(body.name(), body.description(), isCompleted, body.categoryId());
    }}

    @GetMapping("/{{id}}")
    public {item_class} get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {{
        return {item_name}s.findById(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "{item_name} " + id + " not found"));
    }}

    @PostMapping("/{{id}}/complete")
    public {item_class} complete(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {{
        return {item_name}s.complete(id)
            .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "{item_name} " + id + " not found"));
    }}

    public record Create{item_class}Request(String name, String description, Boolean isCompleted, Long categoryId) {{
    }}

    public static class ApiException extends RuntimeException {{
        private final HttpStatus status;

        public ApiException(HttpStatus status, String message) {{
            super(message);
            this.status = status;
        }}

        public HttpStatus status() {{
            return status;
        }}
    }}

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> handleApiException(ApiException ex) {{
        return ResponseEntity.status(ex.status()).body(Map.of(
            "detail", ex.getMessage(),
            "status", ex.status().value()
        ));
    }}
}}
```

Authentication style for this service: `{auth_type}`.
- The AuthUser + JwtAuthInterceptor pattern is already wired globally.
  The controller receives `AuthUser` on every method. No additional
  auth wiring is needed in the controller itself.

Output the COMPLETE file following the pattern above exactly.
No markdown fences, no commentary.

REFERENCE (`controller/ItemController.java`):
---
{template}
---
""",
        },
        {
            "path": "src/test/java/app/marysia/skel/controller/{item_class}ControllerTest.java",
            "template": "src/test/java/app/marysia/skel/ApplicationTests.java",
            "language": "java",
            "description": "test/controller/{item_class}ControllerTest.java — MockMvc integration tests",
            "prompt": """\
Create `test/controller/{item_class}ControllerTest.java` for the
`{item_class}` entity using the same testing pattern as
`ApplicationTests.java`.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure):
- This skeleton uses plain Java RECORDS, NOT JPA entity classes.
- Do NOT import jakarta.persistence.* or jakarta.validation.*.
- Do NOT use @MockBean — this project does NOT use Spring Data JPA or
  Mockito mocking of repositories. Use a REAL Spring context with an
  H2 in-memory database instead.
- Records are IMMUTABLE — you CANNOT call `new {item_class}("name",
  "desc")` because the record has 7 fields. Use the full constructor:
  `new {item_class}(null, "name", "desc", false, null, null, null)`.
- Use JdbcTemplate/JdbcClient for all database access.
- The controller requires JWT authentication via the JwtAuthInterceptor.
  Tests must register a user, obtain a token, and pass it as a Bearer
  header.

Here is the EXACT pattern you MUST follow (modelled after the existing
ApplicationTests.java):

```java
package app.marysia.skel.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {{
    "spring.datasource.url=jdbc:h2:mem:{item_name}test;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa",
    "spring.datasource.password="
}})
class {item_class}ControllerTest {{

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper mapper;

    private String obtainAccessToken() throws Exception {{
        String username = "test-" + UUID.randomUUID().toString().substring(0, 8);
        String registerBody = String.format(
            "{{\\"username\\":\\"%s\\",\\"email\\":\\"%s@example.com\\",\\"password\\":\\"test-password-1234\\"}}",
            username, username
        );
        MvcResult result = mockMvc.perform(post("/api/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(registerBody))
            .andExpect(status().isCreated())
            .andReturn();
        JsonNode json = mapper.readTree(result.getResponse().getContentAsString());
        return json.path("access").asText();
    }}

    @Test
    void list{item_class}s_ReturnsOk() throws Exception {{
        String token = obtainAccessToken();
        mockMvc.perform(get("/api/{items_plural}")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isOk());
    }}

    @Test
    void create{item_class}_ReturnsCreated() throws Exception {{
        String token = obtainAccessToken();
        String body = "{{\\"name\\":\\"Test {item_class}\\",\\"description\\":\\"A test {item_name}\\"}}";
        mockMvc.perform(post("/api/{items_plural}")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated());
    }}

    @Test
    void get{item_class}ById_WhenNotExists_ReturnsNotFound() throws Exception {{
        String token = obtainAccessToken();
        mockMvc.perform(get("/api/{items_plural}/99999")
                .header("Authorization", "Bearer " + token))
            .andExpect(status().isNotFound());
    }}

    @Test
    void anonymousRequest_ReturnsUnauthorized() throws Exception {{
        mockMvc.perform(get("/api/{items_plural}"))
            .andExpect(status().isUnauthorized());
    }}
}}
```

Output the COMPLETE file following the pattern above exactly.
No markdown fences, no commentary.

REFERENCE (`ApplicationTests.java` — shows the auth flow and test style):
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
            "path": "src/main/java/app/marysia/skel/integration/SiblingClients.java",
            "language": "java",
            "description": "integration/SiblingClients.java — typed HTTP clients for sibling backends",
            "prompt": """\
Write `src/main/java/app/marysia/skel/integration/SiblingClients.java`.
The class exposes one typed inner client class per sibling backend in the
wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Package: `app.marysia.skel.integration`.
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
            "path": "src/test/java/app/marysia/skel/integration/IntegrationTest.java",
            "language": "java",
            "description": "test/integration/IntegrationTest.java — cross-service JUnit 5 cases",
            "prompt": """\
Write `src/test/java/app/marysia/skel/integration/IntegrationTest.java`.
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
- `app.marysia.skel.config.JwtProperties`
- (when {sibling_count} > 0) `app.marysia.skel.integration.SiblingClients`

Use 4-space indentation. Output the full file contents only.
""",
        },
    ],
}
