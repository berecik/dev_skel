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

## Generated Project Layout

When you generate a Spring Boot project, the target path is the **wrapper directory** (`main_dir`) and the real service lives in an inner `service/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./service/run, ./service/test, ...
  service/       # real Spring Boot project (pom.xml, src/, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `service/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./service/test / mvn test)
./test

# Start development server
./run dev

# Start production server (from JAR)
./run prod

# Build JAR only
./build --jar

# Build and run in Docker
./build
./run docker

# Stop services
./stop
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run Maven tests |
| `./build` | Build Docker image (`--jar` for JAR only, `--tag=NAME`, `--no-cache`) |
| `./run` | Run server (`dev`, `prod`, `docker`) |
| `./stop` | Stop Docker container |

## Testing

Test the skeleton (E2E):
```bash
cd _skels/java-spring-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

Generally excludes `Makefile` and `merge` only (project content comes from Spring Initializr).
