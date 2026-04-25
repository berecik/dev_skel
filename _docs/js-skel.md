# js-skel

**Location**: `_skels/js-skel/`

**Framework**: Plain JavaScript/Node.js

## Structure

```
js-skel/
├── Makefile
├── .gitignore
├── .editorconfig
├── .prettierrc
├── eslint.config.js
├── src/
│   ├── index.js
│   └── index.test.js
└── (node_modules, package-lock.json - copied)
```

## Generation Notes

- Uses `npm init -y` to create package.json
- Copies skeleton files
- Runs `npm install`

## Generation

From repo root:
```bash
make gen-js NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen js <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Layout

When you generate a JS/Node.js project, the target path is the **wrapper directory** (`main_dir`) and the real Node app lives in an inner `app/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./app/run, ./app/test, ...
  app/           # real Node.js project (package.json, src/, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `app/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./app/test)
./test

# Start development server (delegates to ./app/run)
./run dev

# Start production server
./run prod

# Build and run in Docker
./build
./run docker

# Stop services
./stop
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run Node.js tests |
| `./build` | Build Docker image (`--tag=NAME`, `--no-cache`, `--push`) |
| `./run` | Run server (`dev`, `prod`, `docker`) |
| `./stop` | Stop Docker container |

## Testing

Test the skeleton (E2E):
```bash
cd _skels/js-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

### Merge Script Exclusions

- `package.json`
- `package-lock.json`
