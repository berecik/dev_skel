# rust-actix-skel

**Location**: `_skels/rust-actix-skel/`

**Framework**: Actix-web

## Structure

```
rust-actix-skel/
├── Makefile
├── .env.example
├── Cargo.toml
├── Cargo.lock
└── src/
    └── main.rs
```

## Dependencies

From Cargo.toml:
- actix-web
- actix-rt
- serde (with derive)
- tokio

## Generation Notes

- Uses `cargo new` to create base project
- Removes generated `Cargo.toml` and `src/main.rs`
- Copies skeleton versions
- Runs `cargo fetch`

## Generation

From repo root:
```bash
make gen-rust-actix NAME=<target-path>
```

From anywhere:
```bash
_bin/skel-gen rust-actix <target-path>
```

From skeleton dir:
```bash
./gen <target-path>
```

## Generated Project Layout

When you generate an Actix-web service, the target path is the **wrapper directory** (`main_dir`) and the real service lives in an inner `service/` directory (`project_dir`):

```text
myapp/
  README.md      # generic wrapper README (created by common-wrapper.sh)
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts that call ./service/run, ./service/test, ...
  service/       # real Actix-web project (Cargo.toml, src/, etc.)
```

Wrapper scripts in `myapp/` forward all arguments to the corresponding scripts in `service/`.

## Generated Project Usage

```bash
cd myapp

# Run tests (delegates to ./service/test / cargo test)
./test

# Start development server (delegates to ./service/run)
./run dev

# Start production server (release binary)
./run prod

# Run with cargo-watch (auto-reload)
./run watch

# Build release binary only
./build --release

# Build and run in Docker
./build
./run docker

# Stop services
./stop
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `./test` | Run cargo tests |
| `./build` | Build Docker image (`--release` for binary only, `--tag=NAME`, `--no-cache`) |
| `./run` | Run server (`dev`, `prod`, `watch`, `docker`) |
| `./stop` | Stop Docker container |

## Testing

Test the skeleton (E2E):
```bash
cd _skels/rust-actix-skel
make test
```

## Merge Script

This skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`. It copies auxiliary files into the generated project without overwriting generator-owned files.

### Merge Script Exclusions

- `Cargo.toml`
- `src/main.rs` (leaves these from `cargo new`)
