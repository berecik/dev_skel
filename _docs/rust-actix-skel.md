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

## Generated Project Usage

```bash
cd myapp
cargo run
cargo test
```

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
