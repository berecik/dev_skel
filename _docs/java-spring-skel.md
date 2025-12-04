# java-spring-skel

**Location**: `_skels/java-spring-skel/`

**Framework**: Spring Boot

## Structure

```
java-spring-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/example/skel/
│   │   │   ├── Application.java
│   │   │   ├── controller/
│   │   │   │   ├── RootController.java
│   │   │   │   └── ItemController.java
│   │   │   ├── model/
│   │   │   │   └── Item.java
│   │   │   ├── repository/
│   │   │   │   └── ItemRepository.java
│   │   │   └── service/
│   │   │       └── ItemService.java
│   │   └── resources/
│   │       ├── application.properties
│   │       └── application-prod.properties
│   └── test/java/com/example/skel/
│       ├── ApplicationTests.java
│       └── controller/
│           └── ItemControllerTest.java
└── (target/ - not copied)
```

## Dependencies

From pom.xml:
- Spring Boot Starter Web
- Spring Boot Starter Data JPA
- H2 Database
- Spring Boot Starter Test

## Generation Notes

- Simply copies all skeleton files
- Runs `mvn dependency:resolve`

## Generation

From repo root:
```bash
make gen-java-spring NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen java-spring <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Usage

```bash
cd myapp
mvn spring-boot:run
mvn test
```

## Testing

Test the skeleton (E2E):
```bash
cd _skels/java-spring-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

Generally excludes `Makefile` and `merge` only (project content comes from Spring Initializr).
