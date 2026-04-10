"""AI manifest for the ``java-spring-skel`` skeleton.

The Spring Boot skeleton already ships an `Item` JPA entity + repository +
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
- Use Spring Boot 3.x + Spring Data JPA + jakarta validation. Do NOT
  introduce new dependencies — the pom.xml already has everything you
  need (`spring-boot-starter-web`, `spring-boot-starter-data-jpa`,
  `spring-boot-starter-validation`, `spring-boot-starter-actuator`).
- Use `org.springframework.web.bind.annotation.*` for the REST layer
  and `jakarta.persistence.*` + `jakarta.validation.constraints.*` for
  the entity layer.
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
            "description": "model/{item_class}.java — JPA entity (table `{items_plural}`)",
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
            "description": "repository/{item_class}Repository.java — JPA repository",
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
