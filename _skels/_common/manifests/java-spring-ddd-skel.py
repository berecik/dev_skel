"""AI manifest for the ``java-spring-ddd-skel`` skeleton.

This manifest exists separately from ``java-spring-skel.py`` because the
two skeletons disagree on **where source files live** AND on **how
persistence is wired**, even though their HTTP contract is identical.

- ``java-spring-skel`` (flat) keeps every CRUD endpoint as
  ``model/Item.java`` (a Java ``record``) plus
  ``repository/ItemRepository.java`` (a concrete ``@Repository`` class
  using ``JdbcTemplate`` / ``JdbcClient``) plus ``service/`` plus
  ``controller/`` — three sibling packages under
  ``com.example.skel`` (the legacy package). The flat skel uses **plain
  JDBC, no JPA, no Bean Validation**.
- ``java-spring-ddd-skel`` follows the canonical FastAPI shape: each
  resource is a self-contained module under
  ``app.marysia.skel.<resource>/`` with the four-file split
  ``<Entity>.java`` / ``<Entity>Repository.java`` /
  ``<Entity>Service.java`` / ``<Entity>Controller.java`` plus a
  ``dto/`` sub-package for request bodies. The DDD skel uses
  **Spring Data JPA + Hibernate**, with entity classes carrying
  ``@Entity`` / ``@Table`` annotations. Cross-resource queries (e.g.
  "find items by category id") live on the repository that owns the
  queried entity. Domain errors are sentinel ``DomainException``
  subclasses translated to HTTP via the global
  ``GlobalExceptionHandler``.

Re-using the flat manifest produced AI output that landed in the wrong
place: it created ``model/<Item>.java`` (which does not exist in the DDD
layout), used ``JdbcTemplate`` (which the DDD skel rejects in favour of
JPA), and used the ``com.example.skel`` package (the DDD skel migrated
to ``app.marysia.skel``). This file replaces that stub with a DDD-aware
prompt set.

See ``_docs/DDD-SKELETONS.md`` for the cross-stack DDD layer rules.
"""

SYSTEM_PROMPT = """\
You are a senior Spring Boot 3 engineer regenerating one source file
inside the dev_skel `{skeleton_name}` skeleton. This skeleton uses the
canonical FastAPI shape: every CRUD resource is a self-contained module
under `app.marysia.skel.<resource>/` with a fixed four-file split plus a
`dto/` sub-package.

Project layout (CRITICAL — read carefully):
- The Maven project lives at the root of the service directory
  (`{service_subdir}/`) with the base package `app.marysia.skel`.
- The on-disk service directory inside the wrapper `{project_name}/` is
  `{service_subdir}/`.
- The legacy `com.example.skel` package is GONE — NEVER use it.
- Every resource module follows this layout:
    src/main/java/app/marysia/skel/<resource>/
      <Entity>.java               -- JPA entity (@Entity, @Table)
      <Entity>Repository.java     -- extends JpaRepository<Entity, Long>
      <Entity>Service.java        -- @Service, business logic
      <Entity>Controller.java     -- @RestController, thin HTTP layer
      dto/
        New<Entity>Request.java   -- record for POST body
        <Entity>UpdateRequest.java -- record for PATCH body (when needed)
- The reference resource is `items` (table `items`). The user is adding
  a new resource `{item_name}/` with entity `{item_class}` (snake_case
  `{item_name}`, plural `{items_plural}`).
- The DB table for the new entity MUST be named `{items_plural}` so it
  collides cleanly with other backends in the same wrapper that use the
  same table name (the dev_skel shared-DB integration test relies on
  this).

Layer rules (NON-NEGOTIABLE):
1. **Controllers are thin.** They extract the principal via an
   `AuthUser user` parameter (resolved by `AuthUserArgumentResolver`),
   parse `@RequestBody` DTOs, call ONE service method, and return a
   value (Spring serialises it) or `ResponseEntity<DTO>` when a
   non-200 status is needed (201 on create, 204 on delete). Controllers
   NEVER touch repositories or `EntityManager` directly.
2. **Services orchestrate.** `@Service` classes constructor-injected
   with `JpaRepository` instances. They throw `DomainException`
   subclasses from `app.marysia.skel.shared` — NEVER raw
   `EmptyResultDataAccessException`, `ConstraintViolationException`,
   or `EntityNotFoundException`.
3. **Cross-resource queries live on the repository that owns the
   queried entity.** If the new resource needs to find rows owned by
   `Category`, add the finder method on `CategoryRepository`, not on
   the new resource's repository.
4. **DTOs are explicit.** Don't return JPA entities from controllers
   when the wire shape diverges from the entity. The reference `items`
   resource happens to return `Item` directly because Jackson can
   serialise it cleanly via the global SNAKE_CASE naming strategy —
   follow the same approach unless the user's `{item_class}` needs a
   projection.
5. **`Application.java` does NOT need editing.** Spring Boot's default
   component scan covers every package under `app.marysia.skel`, so the
   new `{item_name}` package is picked up automatically.

Available shared helpers (verified in
`src/main/java/app/marysia/skel/shared/`):
- `DomainException` (abstract base, holds an `HttpStatus`).
- `NotFoundException` -> 404.
- `ConflictException` -> 409.
- `ValidationException` -> 400.
- `UnauthorizedException` -> 401.
- `GlobalExceptionHandler` (`@RestControllerAdvice`) maps every
  `DomainException` subclass plus `HttpMessageNotReadableException`,
  `MethodArgumentNotValidException`, and a catch-all `Exception` to
  the wrapper-shared `{{detail, status}}` JSON envelope.

Auth (verified in `src/main/java/app/marysia/skel/auth/`):
- `AuthUser` is a `public record AuthUser(long id, String username)`.
  It is NOT a Spring Security `UserDetails` and is NOT injected via
  `@AuthenticationPrincipal`. Controllers declare a plain
  `AuthUser user` parameter; `AuthUserArgumentResolver` (a
  `HandlerMethodArgumentResolver` registered in `WebMvcConfig`)
  resolves it from the request attribute set by
  `JwtAuthInterceptor.AUTH_USER_ATTR`.
- The interceptor itself is wired globally in `WebMvcConfig` against
  the same paths the controllers expose. Do NOT add
  `@AuthenticationPrincipal`, `@PreAuthorize`, or any Spring Security
  filter chain code — Spring Security is intentionally NOT on the
  classpath.
- The JWT secret comes from the
  `app.marysia.skel.config.JwtProperties` `@ConfigurationProperties`
  bean (registered via `@ConfigurationPropertiesScan` on
  `Application`). Inject the bean wherever you need the secret —
  NEVER hardcode it.

JPA conventions (CRITICAL — this skel uses JPA, NOT plain JDBC):
- Entities: `@Entity @Table(name = "{items_plural}")`,
  `@Id @GeneratedValue(strategy = GenerationType.IDENTITY)`,
  `@Column(nullable = false)`, `@ManyToOne(fetch = FetchType.LAZY)`,
  `@JoinColumn(name = "category_id")`. Use
  `@OnDelete(action = OnDeleteAction.SET_NULL)` from
  `org.hibernate.annotations` for SET_NULL FK semantics (matches the
  django-bolt `on_delete=SET_NULL` contract for cross-backend table
  parity). Use `@CreationTimestamp` / `@UpdateTimestamp` from
  `org.hibernate.annotations` on `LocalDateTime` audit fields — Hibernate
  populates them automatically; NEVER set them manually in code.
- Entities must have a no-arg constructor (JPA requirement) plus any
  convenience constructors the service uses. Mutable getters/setters
  for every persisted field. Records are NOT used for entities
  (records are immutable; JPA needs setters for lazy proxies).
- Repositories: `extends JpaRepository<{item_class}, Long>` (interface,
  Spring Data generates the impl). Annotate with `@Repository` for
  clarity. Add derived query methods like
  `findAllByOrderByCreatedAtDescIdDesc()` to preserve the
  "newest first" wire-shape contract the React frontend depends on.
- Do NOT import `org.springframework.jdbc.*` — JDBC is NOT used here.
- Do NOT use `JdbcTemplate`, `JdbcClient`, `RowMapper`, or
  hand-written SQL strings. Hibernate handles persistence.

JSON shape (wrapper-shared contract):
- Jackson global naming strategy is `SNAKE_CASE` (set in
  `application.properties` via
  `spring.jackson.property-naming-strategy=SNAKE_CASE`). Most camelCase
  Java fields auto-convert (`createdAt` -> `created_at`,
  `categoryId` -> `category_id`).
- Boolean fields whose Java name starts with `is` (e.g.
  `isCompleted`) need explicit
  `@com.fasterxml.jackson.annotation.JsonProperty("is_completed")` on
  BOTH the getter (`isCompleted()`) and the setter (`setCompleted()`)
  to preserve the `is_` prefix on the wire — Jackson otherwise drops
  the `is` and serialises as `completed`.
- Optional / nullable FKs use boxed types: `Long categoryId`, NOT
  `long categoryId`. The entity may hold a lazy `@ManyToOne` reference
  AND expose a `Long getCategoryId()` convenience method for the wire
  shape (see the reference `Item.java`).

Validation (CRITICAL):
- `spring-boot-starter-validation` is NOT on the classpath. Jakarta
  Bean Validation annotations (`@NotBlank`, `@NotNull`, `@Size`,
  `@Min`, `@Max`, `@Valid`) DO NOT WORK at runtime even if you import
  them — they are silently ignored.
- Do NOT add validation annotations to DTO records. Validate manually
  in the service layer instead, throwing `ValidationException` with a
  descriptive message:

      if (body == null || body.name() == null || body.name().isBlank()) {{
          throw new ValidationException("{item_name} name cannot be empty");
      }}

  This matches the existing `ItemService.create()` pattern.

Shared environment (every backend in the wrapper relies on the same
env vars from `<wrapper>/.env`):
- `${{SPRING_DATASOURCE_URL}}` / `${{DATABASE_JDBC_URL}}` — common
  database. Already wired in `application.properties`. Do NOT touch
  `application.properties` from these prompts.
- `${{JWT_SECRET}}` / `${{JWT_ALGORITHM}}` / `${{JWT_ISSUER}}` /
  `${{JWT_ACCESS_TTL}}` / `${{JWT_REFRESH_TTL}}` — exposed via
  `JwtProperties`. NEVER hardcode the secret.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Match indentation (4 spaces), brace style, and import order of the
  reference resource (`items/`) exactly.
- Group imports as: project (`app.marysia.skel.*`), blank line,
  third-party (`org.springframework.*`, `org.hibernate.*`,
  `com.fasterxml.*`, `jakarta.*`), blank line, stdlib (`java.*`).
- Replace every `Item` / `item` / `items` token with `{item_class}` /
  `{item_name}` / `{items_plural}` — including `@Table(name = "...")`,
  `@RequestMapping("/api/...")`, package fragments, field names,
  variable names.
- Do NOT introduce new dependencies — the pom.xml already has
  `spring-boot-starter-data-jpa`, `hibernate-community-dialects`,
  `spring-boot-starter-web`, `spring-security-crypto`, and `jjwt-*`.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""


MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `mvn -q package -DskipTests` after generation to confirm the "
        "new app.marysia.skel.{item_name}/ module compiles. The "
        "wrapper-shared <wrapper>/.env is already wired in via "
        "application.properties placeholders. No edit to Application.java "
        "is required: Spring Boot's default component scan covers every "
        "package under app.marysia.skel, so the new {item_name} package "
        "is picked up automatically. (NOTE: if a user has added an "
        "explicit @ComponentScan with a narrower base-package filter to "
        "Application.java, they may need to widen it manually — out of "
        "scope for this manifest.)"
    ),
    "targets": [
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/{item_class}.java",
            "template": "src/main/java/app/marysia/skel/items/Item.java",
            "language": "java",
            "description": (
                "{item_name}/{item_class}.java -- JPA entity for the "
                "`{items_plural}` table"
            ),
            "prompt": """\
Create `src/main/java/app/marysia/skel/{item_name}/{item_class}.java` --
the JPA entity backing the `{items_plural}` table.

CRITICAL CONSTRAINTS (violating ANY of these causes a compilation failure
or wrong wire shape):
- This skeleton uses JPA + Hibernate, NOT plain JDBC. Use
  `jakarta.persistence.*` annotations.
- Entities are MUTABLE classes with a no-arg constructor and getter/
  setter pairs for every field. Do NOT use a Java `record` — JPA needs
  setters for lazy proxies.
- Package: `app.marysia.skel.{item_name}` (NOT `com.example.skel.*`).
- Table name MUST be `{items_plural}` so the wrapper-shared SQLite DB
  matches every other backend.
- Use Hibernate's `@CreationTimestamp` / `@UpdateTimestamp` for
  `LocalDateTime createdAt` / `LocalDateTime updatedAt` audit fields.
  NEVER set them in user code.
- Boolean fields starting with `is` (e.g. `isCompleted`) need
  `@JsonProperty("is_completed")` on BOTH the getter `isCompleted()`
  and the setter `setCompleted(boolean)` to preserve the `is_` prefix
  on the wire (Jackson otherwise drops the `is` prefix). Other
  camelCase fields auto-convert via the global SNAKE_CASE naming
  strategy and do NOT need explicit `@JsonProperty` annotations.
- Cross-resource FK to Category: use a lazy
  `@ManyToOne(fetch = FetchType.LAZY)` association annotated with
  `@JoinColumn(name = "category_id")` and
  `@OnDelete(action = OnDeleteAction.SET_NULL)` from
  `org.hibernate.annotations`. Annotate the field with `@JsonIgnore`
  and expose a `Long getCategoryId()` convenience method that returns
  `category == null ? null : category.getId()` so the wire shape stays
  `category_id: <long|null>` (matching the django-bolt contract). Drop
  the category FK if `{item_class}` does not need it; mirror the
  reference shape otherwise.
- Field layout suggested for `{item_class}` (mirror Item.java's shape;
  drop fields that don't apply to the user's `{item_class}`):
    - `Long id` (`@Id @GeneratedValue(strategy = GenerationType.IDENTITY)`)
    - `String name` (`@Column(nullable = false)`)
    - `String description` (`@Column(columnDefinition = "TEXT")`)
    - `boolean isCompleted` (`@Column(name = "is_completed", nullable = false)`)
    - `Category category` (lazy ManyToOne, see above) — keep this only
      if the user's `{item_class}` is conceptually scoped by category;
      otherwise omit and drop the cross-package import.
    - `LocalDateTime createdAt` (`@CreationTimestamp`,
      `@Column(name = "created_at", nullable = false, updatable = false)`)
    - `LocalDateTime updatedAt` (`@UpdateTimestamp`,
      `@Column(name = "updated_at", nullable = false)`)
- Provide:
    - A no-arg constructor (JPA requirement).
    - A convenience constructor that accepts the user-settable fields
      (mirrors `Item(String name, String description, boolean isCompleted, Category category)`).
    - Getters and setters for every persisted field.
    - The `getCategoryId()` convenience method when the FK is present.

Authentication style for this service: `{auth_type}`. (Auth is wired
globally; the entity itself is auth-agnostic.)

REFERENCE (`items/Item.java` -- adapt the structure for `{item_class}`,
preserving the ManyToOne FK pattern, the @JsonProperty on the boolean
getter/setter, and the `getCategoryId()` convenience method):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/{item_class}Repository.java",
            "template": "src/main/java/app/marysia/skel/items/ItemRepository.java",
            "language": "java",
            "description": (
                "{item_name}/{item_class}Repository.java -- Spring Data "
                "JPA repository"
            ),
            "prompt": """\
Create
`src/main/java/app/marysia/skel/{item_name}/{item_class}Repository.java`.

CRITICAL CONSTRAINTS:
- This is a Spring Data JPA INTERFACE, NOT a concrete class. Spring
  generates the implementation at runtime.
- Extend `JpaRepository<{item_class}, Long>` (entity type +
  primary-key type).
- Import `org.springframework.data.jpa.repository.JpaRepository`.
- Annotate with `@Repository` for clarity (the reference does this).
- Do NOT import `org.springframework.jdbc.*` — JDBC is NOT used here.
- Do NOT redeclare `save`, `findById`, `findAll`, or `deleteById` —
  they are inherited from `JpaRepository` already.

Required derived query methods:
- `findAllByOrderByCreatedAtDescIdDesc()` -> `List<{item_class}>`.
  Preserves the "newest first" ordering the React frontend relies on
  (matches the SQL `ORDER BY created_at DESC, id DESC` used by the
  flat skeleton's hand-written query). Spring Data parses the method
  name and generates the JPQL automatically.

If the user's `{item_class}` has a category FK, ALSO add cross-resource
finder methods on the COUNTERPART repository (e.g.
`Items.findByCategoryId`) — but those go on
`CategoryRepository`/this repository following the
"queries live on the repository that owns the queried entity" rule.
For this manifest target, only declare finders that query rows of
THIS entity.

Package: `app.marysia.skel.{item_name}`.

REFERENCE (`items/ItemRepository.java`):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/{item_class}Service.java",
            "template": "src/main/java/app/marysia/skel/items/ItemService.java",
            "language": "java",
            "description": (
                "{item_name}/{item_class}Service.java -- @Service business "
                "logic"
            ),
            "prompt": """\
Create
`src/main/java/app/marysia/skel/{item_name}/{item_class}Service.java`.

CRITICAL CONSTRAINTS:
- Annotate with `@Service`.
- Constructor-injected with `{item_class}Repository` (and any
  cross-resource repositories the service needs — e.g.
  `CategoryRepository` if the user's entity has a category FK).
- Do NOT use `@Transactional` unless absolutely needed — Spring Data
  JPA wraps individual repository methods in their own transactions,
  which is sufficient for the wrapper-shared CRUD contract.
- Throw `app.marysia.skel.shared.NotFoundException`,
  `ConflictException`, `ValidationException`, or `UnauthorizedException`
  on domain errors. NEVER let `EmptyResultDataAccessException`,
  `EntityNotFoundException`, or `ConstraintViolationException` escape
  the service layer.
- Manually validate `@RequestBody` DTOs because Bean Validation is NOT
  on the classpath. Throw `ValidationException("...")` with a
  descriptive detail message. Mirror the existing
  `ItemService.create()` shape:

      if (body == null || body.name() == null || body.name().isBlank()) {{
          throw new ValidationException("{item_name} name cannot be empty");
      }}

- Resolve cross-resource FKs by calling
  `<otherRepo>.findById(...).orElseThrow(() -> new ValidationException(...))`
  before constructing the entity, so a stale FK fails fast with a 400
  instead of a 500.

Required methods (drop or extend based on `{item_class}`'s natural
operations; mirror the items service for parity with the wrapper-shared
contract):
- `List<{item_class}> list()` -> calls
  `repo.findAllByOrderByCreatedAtDescIdDesc()`.
- `{item_class} get(long id)` -> calls `repo.findById(id)` and throws
  `NotFoundException("{item_name} " + id + " not found")` when empty.
- `{item_class} create(New{item_class}Request body)` -> validates the
  body, resolves any FK references, constructs the entity, calls
  `repo.save(...)`, returns the saved entity.
- `{item_class} update(long id, {item_class}UpdateRequest patch)` ->
  calls `get(id)` (so 404 propagates), applies non-null patch fields
  to the entity (using setters), calls `repo.save(...)`, returns the
  updated entity. Each patch field on the DTO is `Optional<T>` or a
  nullable boxed type; only mutate when present/non-null.
- `void delete(long id)` -> calls `get(id)` (for 404 parity) then
  `repo.deleteById(id)`.
- `{item_class} complete(long id)` -> ONLY add this when the user's
  entity has a boolean `isCompleted` field (i.e. when the entity
  mirrors the canonical Item shape). Idempotent: completing an
  already-completed row is a no-op that still returns 200.

Package: `app.marysia.skel.{item_name}`.

REFERENCE (`items/ItemService.java` -- preserves the
constructor-injection, validation, FK-resolution, and idempotent-
complete pattern; adapt for `{item_class}`):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/{item_class}Controller.java",
            "template": "src/main/java/app/marysia/skel/items/ItemController.java",
            "language": "java",
            "description": (
                "{item_name}/{item_class}Controller.java -- thin REST "
                "controller mounting /api/{items_plural}"
            ),
            "prompt": """\
Create
`src/main/java/app/marysia/skel/{item_name}/{item_class}Controller.java`.

CRITICAL CONSTRAINTS:
- `@RestController @RequestMapping("/api/{items_plural}")`.
- Constructor-injected with `{item_class}Service` (NOT the repository
  — the controller never touches the data layer).
- Every handler method declares an `AuthUser user` parameter so future
  ownership tightening does not need to add a new parameter to each
  method. The principal is resolved by `AuthUserArgumentResolver`
  from `app.marysia.skel.auth` — do NOT use `@AuthenticationPrincipal`
  (Spring Security is NOT on the classpath; the resolver is wired via
  `WebMvcConfig`). Mark the parameter
  `@SuppressWarnings("unused") AuthUser user` to silence the unused-
  param warning, exactly as the reference does. The principal is
  unused at the route level today.
- Parse JSON bodies via `@RequestBody New{item_class}Request body` (and
  `{item_class}UpdateRequest` on PATCH/PUT). Do NOT add `@Valid` —
  Bean Validation is NOT on the classpath; validation lives in the
  service layer.
- Return values are auto-serialised by Spring + Jackson. Use
  `@ResponseStatus(HttpStatus.CREATED)` on POST create. Return
  `void` (or `ResponseEntity<Void>`) with
  `@ResponseStatus(HttpStatus.NO_CONTENT)` on DELETE.
- The controller does NOT define an inner `ApiException` class or its
  own `@ExceptionHandler` — the cross-cutting
  `app.marysia.skel.shared.GlobalExceptionHandler` already handles
  every `DomainException` subclass. Throw `NotFoundException` etc.
  from the service and let the handler translate.

Required endpoints (mirror the items controller; drop endpoints the
user's `{item_class}` does not need):
- `GET    /api/{items_plural}`           -> `service.list()`
- `POST   /api/{items_plural}`           -> `service.create(body)`
  (annotated `@ResponseStatus(HttpStatus.CREATED)`)
- `GET    /api/{items_plural}/{{id}}`    -> `service.get(id)`
- `PATCH  /api/{items_plural}/{{id}}`    -> `service.update(id, body)`
  (when the user adds an UpdateRequest DTO)
- `DELETE /api/{items_plural}/{{id}}`    -> `service.delete(id)`
  (annotated `@ResponseStatus(HttpStatus.NO_CONTENT)`, returns void)
- `POST   /api/{items_plural}/{{id}}/complete` -> `service.complete(id)`
  (ONLY when the entity has the boolean `isCompleted` field)

Each handler signature follows the reference:

    @GetMapping
    public List<{item_class}> list(@SuppressWarnings("unused") AuthUser user) {{
        return service.list();
    }}

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public {item_class} create(@SuppressWarnings("unused") AuthUser user,
                       @RequestBody New{item_class}Request body) {{
        return service.create(body);
    }}

    @GetMapping("/{{id}}")
    public {item_class} get(@SuppressWarnings("unused") AuthUser user, @PathVariable long id) {{
        return service.get(id);
    }}

Authentication style for this service: `{auth_type}`. The
`JwtAuthInterceptor` + `AuthUserArgumentResolver` pattern is wired
globally via `WebMvcConfig` -- the controller receives `AuthUser` on
every method. No additional auth wiring is needed in the controller
itself.

Package: `app.marysia.skel.{item_name}`.

REFERENCE (`items/ItemController.java`):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/dto/New{item_class}Request.java",
            "template": "src/main/java/app/marysia/skel/items/dto/NewItemRequest.java",
            "language": "java",
            "description": (
                "{item_name}/dto/New{item_class}Request.java -- record for "
                "POST /api/{items_plural} body"
            ),
            "prompt": """\
Create
`src/main/java/app/marysia/skel/{item_name}/dto/New{item_class}Request.java`.

CRITICAL CONSTRAINTS:
- This is a Java `record` (immutable), NOT a class.
- Package: `app.marysia.skel.{item_name}.dto`.
- Do NOT add Jakarta Bean Validation annotations (`@NotBlank`,
  `@NotNull`, `@Size`, etc.) — `spring-boot-starter-validation` is
  NOT on the classpath. Validation lives in the service layer
  (`{item_class}Service.create()` throws `ValidationException`).
- Jackson maps the incoming snake_case JSON keys onto these camelCase
  record components automatically because of the global SNAKE_CASE
  naming strategy in `application.properties`. NO `@JsonProperty`
  annotations are needed on record components for plain camelCase
  fields. (Boolean fields starting with `is` would need explicit
  `@JsonProperty("is_<rest>")` if record components used the `is`
  prefix — but for record components Jackson treats them as plain
  property names, so naming them `isCompleted` produces the wire key
  `is_completed` correctly.)
- Use boxed types (`Boolean`, `Long`) for fields that are optional on
  the wire — that lets the service layer distinguish "absent" from
  "false" / "0" via `body.isCompleted() == null` checks (mirrors the
  reference).

Suggested field layout for the canonical Item shape (drop fields that
don't apply to `{item_class}`; add fields the user's entity needs):
- `String name`
- `String description`
- `Boolean isCompleted`
- `Long categoryId`

Match the reference verbatim except for entity / type names.

REFERENCE (`items/dto/NewItemRequest.java`):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/main/java/app/marysia/skel/{item_name}/dto/{item_class}UpdateRequest.java",
            "template": "src/main/java/app/marysia/skel/items/dto/NewItemRequest.java",
            "language": "java",
            "description": (
                "{item_name}/dto/{item_class}UpdateRequest.java -- record "
                "for PATCH /api/{items_plural}/{{id}} body"
            ),
            "prompt": """\
Create
`src/main/java/app/marysia/skel/{item_name}/dto/{item_class}UpdateRequest.java`.

CRITICAL CONSTRAINTS:
- This is a Java `record` (immutable), NOT a class.
- Package: `app.marysia.skel.{item_name}.dto`.
- Partial-update semantics: every component is OPTIONAL. Use boxed
  types (`String`, `Boolean`, `Long`) so a `null` value means
  "leave field unchanged". The service layer checks each component
  with `if (patch.<field>() != null) entity.set<Field>(patch.<field>())`.
  Do NOT use `Optional<T>` for record components — Jackson does not
  deserialise `Optional` cleanly without extra modules.
- Do NOT add Jakarta Bean Validation annotations —
  `spring-boot-starter-validation` is NOT on the classpath.
- Jackson maps incoming snake_case JSON keys onto camelCase record
  components automatically via the global SNAKE_CASE naming strategy.
  No `@JsonProperty` annotations required for plain camelCase fields.

Suggested field layout (drop fields that should not be user-mutable
post-create, e.g. `id`, `createdAt`, `updatedAt`):
- `String name`
- `String description`
- `Boolean isCompleted`
- `Long categoryId`

Note: the existing `items/dto/` directory ships ONLY a
`NewItemRequest` (no update DTO) because the canonical items resource
exposes a `complete` endpoint instead of a generic PATCH. For the
user's `{item_class}` we add an explicit update record so the
controller can support PATCH `/api/{items_plural}/{{id}}` cleanly.
The reference template below is `NewItemRequest.java` — use it for
formatting and SNAKE_CASE handling cues, then rename to
`{item_class}UpdateRequest` and adjust the record components for
partial-update semantics (every component nullable).

REFERENCE (`items/dto/NewItemRequest.java` -- shape & formatting cue;
the actual semantics are partial-update):
---
{template}
---

Output the COMPLETE file. No markdown fences, no commentary.
""",
        },
    ],
}


# --------------------------------------------------------------------------- #
#  Integration manifest (second Ollama session)
# --------------------------------------------------------------------------- #
#
# After the per-target MANIFEST above generates the new resource module,
# ``_bin/skel-gen-ai`` runs a second Ollama pass against the block below
# to add cross-service clients + integration tests. Mirrors the flat
# ``java-spring-skel`` integration manifest but with paths and prompt
# text updated for the DDD layout: integration code lands under
# ``app.marysia.skel.integrations`` (a sibling top-level resource module
# dedicated to outbound HTTP), and tests reside in
# ``src/test/java/app/marysia/skel/integrations/IntegrationTest.java``.


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Spring Boot 3 engineer integrating a freshly generated
service into an existing dev_skel multi-service wrapper. The service
uses the DDD per-resource layout: each CRUD resource lives under
`app.marysia.skel.<resource>/` with the four-file split (entity /
repository / service / controller) plus a `dto/` sub-package.

The new service is `{service_label}` (slug `{service_slug}`, tech
`java-spring-ddd-skel`). It already ships:
- The wrapper-shared `Item` resource at `app.marysia.skel.items/`
  mounted at `/api/items` using JPA + Hibernate (NOT JDBC).
- Wrapper-shared `categories`, `orders`, `catalog`, and `state`
  resource modules.
- A user-chosen `{item_class}` resource module under
  `app.marysia.skel.{item_name}/` mounted at `/api/{items_plural}`
  (the per-target manifest added it).
- JWT auth via the `JwtProperties` bean (`@ConfigurationProperties`)
  + `JwtAuthInterceptor` -- the secret comes from
  `jwtProperties.getSecret()`. The principal is published as an
  `app.marysia.skel.auth.AuthUser` record onto the request attribute
  and resolved into controller methods by `AuthUserArgumentResolver`.
  NEVER hardcode the secret.
- The wrapper-shared `<wrapper>/.env` is loaded by
  `application.properties` placeholders so `SPRING_DATASOURCE_URL` /
  `DATABASE_JDBC_URL` and the JWT vars are identical to every other
  backend in the project.
- `app.marysia.skel.shared.*` exports the sentinel domain exceptions
  (`DomainException`, `NotFoundException`, `ConflictException`,
  `ValidationException`, `UnauthorizedException`) plus the
  `GlobalExceptionHandler` `@RestControllerAdvice` that maps them to
  the wrapper-shared `{{detail, status}}` JSON envelope.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Your job for this Ollama session is to generate **integration code +
integration tests** that wire the new service into the wrapper:

1. A typed Java client class (under `app.marysia.skel.integrations`)
   for each sibling backend the new service should call. The client
   must read the sibling's URL from
   `System.getenv("SERVICE_URL_<UPPER_SLUG>")` so it picks up the
   auto-allocated port from `_shared/service-urls.env` without any
   per-deployment edits.
2. JUnit 5 integration tests (`@SpringBootTest`) under
   `src/test/java/app/marysia/skel/integrations/` that exercise the
   cross-service flows end-to-end via the wrapper-shared SQLite
   database (and, when sibling backends are present, via the typed
   clients above).

Coding rules:
- Use **Spring Boot 3.x** with JPA (`JpaRepository`). Do NOT use
  `JdbcTemplate` / `JdbcClient` in the integration layer. Do NOT
  introduce new dependencies beyond what the pom.xml already pins.
- Use `RestTemplate` or `java.net.http.HttpClient` for sibling HTTP
  calls. Do NOT add `spring-boot-starter-webflux`, `okhttp`, or any
  other HTTP client library.
- Read JWT material via the `JwtProperties` bean —
  `jwtProperties.getSecret()`. NEVER hardcode the secret.
- Use JUnit 5 (`@Test`, `@BeforeAll`, `Assertions.*`,
  `Assumptions.assumeTrue`) for tests. Guard sibling calls with
  `try/catch` + `Assumptions.assumeTrue(false, "...")` so tests skip
  gracefully when a sibling is unreachable or its env var is unset.
- Throw `app.marysia.skel.shared.DomainException` subclasses (or a
  new `IntegrationException` defined alongside the client) on
  upstream non-2xx responses; do NOT leak raw
  `RestClientException` / `IOException`.
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
        "Integration phase: writes "
        "src/main/java/app/marysia/skel/integrations/SiblingClients.java "
        "and src/test/java/app/marysia/skel/integrations/IntegrationTest.java, "
        "then runs the test-and-fix loop via `./test`."
    ),
    "test_command": "./test",
    "fix_timeout_m": 120,
    "targets": [
        {
            "path": "src/main/java/app/marysia/skel/integrations/SiblingClients.java",
            "language": "java",
            "description": (
                "integrations/SiblingClients.java -- typed HTTP clients "
                "for sibling backends"
            ),
            "prompt": """\
Write
`src/main/java/app/marysia/skel/integrations/SiblingClients.java`.
The class exposes one typed inner client class per sibling backend in
the wrapper.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Package: `app.marysia.skel.integrations`.
- Use `java.net.http.HttpClient` (JDK 21 stdlib) or
  `org.springframework.web.client.RestTemplate` for HTTP calls. Do
  NOT add external HTTP client dependencies.
- Define a top-level `IntegrationException extends RuntimeException`
  carrying an `int statusCode` and `String body` (used when a sibling
  returns non-2xx).
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
      `java.util.Map<String, Object>` respectively (use a Jackson
      `ObjectMapper` field for parsing).
    - Throws `IntegrationException` on non-2xx responses, with the
      status code and response body.
- When `{sibling_count}` is 0, the file should still be syntactically
  valid: define `IntegrationException` and an empty `SiblingClients`
  wrapper class with no inner classes plus a comment
  `// No sibling clients -- {sibling_count} siblings discovered.`
  Do NOT define dummy client classes for non-existent siblings.
- Use 4-space indentation, PascalCase classes, camelCase methods.

Output the full file contents only. No markdown fences, no commentary.
""",
        },
        {
            "path": "src/test/java/app/marysia/skel/integrations/IntegrationTest.java",
            "language": "java",
            "description": (
                "test/integrations/IntegrationTest.java -- cross-service "
                "JUnit 5 cases"
            ),
            "prompt": """\
Write
`src/test/java/app/marysia/skel/integrations/IntegrationTest.java`.
JUnit 5 integration tests that exercise the new `{service_label}`
service end-to-end and (when sibling backends are present) verify the
cross-service flow against them.

Wrapper snapshot:
---
{wrapper_snapshot}
---

CRITICAL RULES:
- Use JUnit 5 (`org.junit.jupiter.api.*`) and Spring Boot Test
  (`@SpringBootTest`). Do NOT use JUnit 4 or TestNG.
- Annotate the class with `@SpringBootTest` and `@AutoConfigureMockMvc`
  so MockMvc is wired automatically. Use a `@TestPropertySource` block
  pinning `spring.datasource.url=jdbc:h2:mem:integ-{item_name}-test;DB_CLOSE_DELAY=-1`
  for hermetic test isolation. Set
  `spring.jpa.hibernate.ddl-auto=create-drop` so Hibernate builds the
  schema on startup.
- Guard sibling client calls with `try/catch` +
  `org.junit.jupiter.api.Assumptions.assumeTrue(false, "...")` so tests
  skip gracefully when the env var is missing or the sibling is
  unreachable.
- Use `MockMvc` for hitting the local service's endpoints during
  tests. Inject the JpaRepository for any direct DB seeding.
- Inject `JwtProperties` to derive the JWT secret; NEVER hardcode it.

Required tests:

1. `testItemsEndpointRoundTrip` -- inject `ItemRepository`, save an
   `Item`, then GET `/api/items` (with a Bearer token obtained via
   the auth flow) and assert the row is present.

2. `testReactStateRoundTrip` -- inject `ReactStateRepository`, save a
   `ReactState` with key="test_key", read it back, assert the value
   matches.

3. `test{item_class}EndpointUsesJwt` -- construct an authenticated
   request to `/api/{items_plural}` and assert HTTP 200 (or 201 on
   POST). Use a token obtained via `obtainAccessToken()` (mirrors the
   `ItemController` test pattern: POST `/api/auth/register` to get an
   access JWT).

4. `testJwtSecretIsWrapperShared` -- assert
   `jwtProperties.getSecret()` is non-null and equals
   `System.getenv("JWT_SECRET")` when the env var is set
   (otherwise just assert non-null; Spring fills it from the
   `application.properties` placeholder default during tests).

5. **When `{sibling_count}` > 0**: add one extra test per sibling
   named `testSibling<PascalSlug>ItemsVisibleViaSharedDb`. Guard
   instantiation like this:
   ```java
   SiblingClients.<PascalSlug>Client client;
   try {{
       client = new SiblingClients.<PascalSlug>Client(token);
   }} catch (IllegalStateException e) {{
       Assumptions.assumeTrue(false, "SERVICE_URL_<SLUG> not set");
       return;
   }}
   try {{
       var rows = client.listItems();
       Assertions.assertNotNull(rows);
   }} catch (Exception e) {{
       Assumptions.assumeTrue(false, "sibling unreachable: " + e.getMessage());
   }}
   ```

6. When `{sibling_count}` is 0, **do NOT add any sibling test**.

Imports (verify none are duplicated):
- `org.junit.jupiter.api.*`
- `org.junit.jupiter.api.Assumptions`
- `org.junit.jupiter.api.Assertions`
- `org.springframework.beans.factory.annotation.Autowired`
- `org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc`
- `org.springframework.boot.test.context.SpringBootTest`
- `org.springframework.test.context.TestPropertySource`
- `org.springframework.test.web.servlet.MockMvc`
- `app.marysia.skel.config.JwtProperties`
- `app.marysia.skel.items.Item` /
  `app.marysia.skel.items.ItemRepository`
- `app.marysia.skel.state.ReactState` /
  `app.marysia.skel.state.ReactStateRepository`
- (when {sibling_count} > 0)
  `app.marysia.skel.integrations.SiblingClients`

Use 4-space indentation. Output the full file contents only.
No markdown fences, no commentary.
""",
        },
    ],
}
