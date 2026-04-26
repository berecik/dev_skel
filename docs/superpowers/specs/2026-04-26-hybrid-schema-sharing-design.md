# Hybrid Backend Schema Sharing Design

## Context

The `_docs/Hybrid Backend Rust Skeleton Design.md` document describes a
future `rust-hybrid-skel` that pairs an Actix-Web CRUD layer (Diesel ORM)
with a FastAPI logic backend. The central unsolved problem: **how do Rust
and Python share the data schema without drift?**

The architecture places Actix as the exclusive data layer — FastAPI never
touches the database directly. FastAPI calls into Actix either in-process
(PyO3 embedded mode) or over the network (gRPC / HTTP remote mode). The
schema contract therefore lives at the FastAPI-to-Actix boundary, not at
the database level.

This spec defines the schema-sharing mechanism: Protocol Buffers as the
single source of truth, with code generation into both Rust (prost/tonic)
and Python (Pydantic models + dual-mode client).

## Architecture Overview

```
                     ┌─────────────┐
                     │  .proto     │  ← single source of truth
                     │  (messages  │
                     │   + service)│
                     └──────┬──────┘
                ┌───────────┴───────────┐
                ▼                       ▼
        prost + tonic              codegen (custom)
        ┌──────────┐              ┌──────────────┐
        │ Rust     │              │ Python       │
        │ structs  │              │ Pydantic     │
        │ + gRPC   │              │ models       │
        │   server │              │ + client     │
        │   trait  │              │   (dual-mode)│
        └────┬─────┘              └──────┬───────┘
             │                           │
             ▼                           │
     ┌───────────────┐                   │
     │ Actix CRUD    │◄──────────────────┘
     │ (Diesel → DB) │   in-process (PyO3)
     │               │   OR gRPC / HTTP
     └───────────────┘
```

**Key properties:**

- One source of truth: `.proto` files
- No drift: both sides generated from the same definition; compile/import
  errors catch mismatches
- Dual mode: embedded (PyO3, zero network hop) vs remote (gRPC/HTTP)
  selected by a single env var (`CRUD_MODE`)
- GIL-safe: `py.allow_threads()` in the PyO3 bridge
- Standard FastAPI: plain Pydantic models (not protobuf wire objects),
  so OpenAPI docs, validation, middleware all work unchanged

## 1. Proto Schema (Source of Truth)

One `.proto` file per domain entity, plus a service definition. Proto
files live at the workspace root in `proto/`.

Example (`proto/items.proto`):

```protobuf
syntax = "proto3";
package hybrid.items;

message Item {
  int64 id = 1;
  string name = 2;
  optional string description = 3;
  bool is_completed = 4;
  optional int64 category_id = 5;
  string created_at = 6;   // ISO8601
  string updated_at = 7;   // ISO8601
}

message CreateItemRequest {
  string name = 1;
  optional string description = 2;
  optional int64 category_id = 3;
}

message UpdateItemRequest {
  int64 id = 1;
  optional string name = 2;
  optional string description = 3;
  optional bool is_completed = 4;
  optional int64 category_id = 5;
}

message ItemId { int64 id = 1; }
message ItemList { repeated Item items = 1; }
message Empty {}

service ItemService {
  rpc List(Empty) returns (ItemList);
  rpc Get(ItemId) returns (Item);
  rpc Create(CreateItemRequest) returns (Item);
  rpc Update(UpdateItemRequest) returns (Item);
  rpc Delete(ItemId) returns (Empty);
  rpc Complete(ItemId) returns (Item);
}
```

The proto separates **Create** (no id, no timestamps — server generates
them), **Update** (all optional except id), and **Response** (full Item
with all fields). This maps directly to the three Pydantic model variants
FastAPI needs.

### Type mapping

| Proto type | Rust (prost) | Python (Pydantic) | SQL (Diesel) |
|------------|-------------|-------------------|-------------|
| `int64` | `i64` | `int` | `BIGINT` / `INTEGER` |
| `int32` | `i32` | `int` | `INTEGER` |
| `string` | `String` | `str` | `TEXT` / `VARCHAR` |
| `bool` | `bool` | `bool` | `BOOLEAN` |
| `float` / `double` | `f32` / `f64` | `float` | `REAL` / `DOUBLE` |
| `optional T` | `Option<T>` | `Optional[T] = None` | `NULLABLE` |
| `repeated T` | `Vec<T>` | `list[T]` | (join table / JSON) |
| `string` (ISO8601) | `String` | `str` | `TEXT` (ISO8601) |

Timestamps are strings in proto (ISO8601 format). The Rust repo layer
formats them from `chrono::NaiveDateTime`; the Python side can coerce
to `datetime` via a Pydantic validator if needed.

## 2. Rust Side: Prost + Tonic + Diesel + PyO3

### Workspace layout

```
rust-hybrid-skel/
├── proto/                    # .proto files (source of truth)
│   └── items.proto
├── common_db/                # Diesel ORM + Prost types + PyO3 bridge
│   ├── src/
│   │   ├── lib.rs            # PyO3 module + re-exports
│   │   ├── schema.rs         # Diesel-generated (diesel print-schema)
│   │   ├── models.rs         # Diesel Insertable/Queryable structs
│   │   ├── repo.rs           # Repository: Diesel <-> Prost conversion
│   │   └── bridge.rs         # #[pyclass] wrappers using pythonize
│   ├── build.rs              # prost_build compiles .proto -> Rust types
│   └── Cargo.toml            # prost, diesel, pyo3, pythonize
├── web_gateway/              # Actix-Web + Tonic gRPC dual server
│   ├── src/
│   │   ├── main.rs           # Starts both HTTP and gRPC listeners
│   │   ├── grpc.rs           # Tonic service impl (calls repo)
│   │   └── http.rs           # Actix handlers (calls same repo)
│   └── Cargo.toml            # actix-web, tonic
└── Cargo.toml                # Workspace root
```

### Data flow inside Rust

```
Proto message (prost struct)
       ↕ conversion in repo.rs
Diesel model (Queryable/Insertable struct)
       ↕ Diesel query
SQLite / Postgres
```

The `repo` module is the **only** place that knows about both Diesel and
Prost. It converts between the two: `DieselItem -> proto::Item` on read,
`proto::CreateItemRequest -> NewItem` on write. Both `grpc.rs` and
`http.rs` call the same repo functions — CRUD logic is written once.

### Repo conversion example

```rust
// repo.rs
use crate::models::{Item as DieselItem, NewItem};
use crate::proto::items::{Item as ProtoItem, CreateItemRequest};

impl From<DieselItem> for ProtoItem {
    fn from(row: DieselItem) -> Self {
        ProtoItem {
            id: row.id as i64,
            name: row.name,
            description: row.description,
            is_completed: row.is_completed,
            category_id: row.category_id.map(|id| id as i64),
            created_at: row.created_at.format("%Y-%m-%dT%H:%M:%.3fZ").to_string(),
            updated_at: row.updated_at.format("%Y-%m-%dT%H:%M:%.3fZ").to_string(),
        }
    }
}

impl From<CreateItemRequest> for NewItem {
    fn from(req: CreateItemRequest) -> Self {
        NewItem {
            name: req.name,
            description: req.description,
            category_id: req.category_id.map(|id| id as i32),
        }
    }
}
```

### PyO3 bridge (embedded mode)

`bridge.rs` exposes repo functions as `#[pyfunction]`s. Uses `pythonize`
crate to convert prost structs to/from Python dicts:

```rust
// bridge.rs
use pyo3::prelude::*;
use pythonize::{depythonize, pythonize};

#[pyfunction]
fn create_item(py: Python, data: PyObject) -> PyResult<PyObject> {
    let req: proto::CreateItemRequest = depythonize(data.bind(py))?;
    let pool = get_pool();   // connection pool stored in a OnceCell
    py.allow_threads(|| {
        let item = repo::create_item(&pool, req)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        Python::with_gil(|py| pythonize(py, &item).map_err(Into::into))
    })
}

#[pyfunction]
fn list_items(py: Python) -> PyResult<PyObject> {
    let pool = get_pool();
    py.allow_threads(|| {
        let items = repo::list_items(&pool)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        Python::with_gil(|py| pythonize(py, &items).map_err(Into::into))
    })
}

#[pymodule]
fn common_db(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(create_item, m)?)?;
    m.add_function(wrap_pyfunction!(list_items, m)?)?;
    // ... other CRUD functions
    Ok(())
}
```

`py.allow_threads()` releases the GIL so FastAPI can keep serving other
async requests while Diesel blocks on the database.

### Cargo.toml (common_db)

```toml
[lib]
crate-type = ["cdylib", "rlib"]
# cdylib = Python extension (.so/.pyd)
# rlib   = Rust library (used by web_gateway)

[dependencies]
prost = "0.13"
diesel = { version = "2", features = ["sqlite"] }
pyo3 = { version = "0.22", features = ["extension-module"] }
pythonize = "0.22"
serde = { version = "1", features = ["derive"] }
chrono = "0.4"

[build-dependencies]
prost-build = "0.13"
```

## 3. Python Side: Generated Pydantic Models + Dual-Mode Client

A codegen step (`make gen-schema`) reads `.proto` files and emits two
Python files into `logic_app/generated/`. Generated files are committed
to git (not gitignored) so that the Python side works without requiring
`protoc` at runtime or install time. The codegen runs only when a
developer edits a `.proto` file — the same "generate then commit"
pattern as Diesel's `schema.rs`.

### Generated Pydantic models

`logic_app/generated/models.py` (auto-generated, committed):

```python
# AUTO-GENERATED from proto/items.proto — do not edit

from pydantic import BaseModel
from typing import Optional

class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_completed: bool
    category_id: Optional[int] = None
    created_at: str
    updated_at: str

class CreateItemRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None

class UpdateItemRequest(BaseModel):
    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    category_id: Optional[int] = None
```

These are plain Pydantic — FastAPI uses them directly as `response_model`
and request body types. OpenAPI docs, validation, middleware all work
unchanged.

### Generated dual-mode client

`logic_app/generated/client.py` (auto-generated, committed):

```python
# AUTO-GENERATED from proto/items.proto — do not edit

from __future__ import annotations
import os
from typing import Protocol
from .models import Item, CreateItemRequest, UpdateItemRequest

class ItemServiceClient(Protocol):
    def list(self) -> list[Item]: ...
    def get(self, id: int) -> Item: ...
    def create(self, req: CreateItemRequest) -> Item: ...
    def update(self, req: UpdateItemRequest) -> Item: ...
    def delete(self, id: int) -> None: ...
    def complete(self, id: int) -> Item: ...

class EmbeddedItemService:
    """In-process calls via PyO3 (zero network hop)."""
    def __init__(self):
        import common_db
        self._db = common_db

    def create(self, req: CreateItemRequest) -> Item:
        raw = self._db.create_item(req.model_dump())
        return Item.model_validate(raw)

    def list(self) -> list[Item]:
        raw = self._db.list_items()
        return [Item.model_validate(r) for r in raw]
    # ... other methods

class GrpcItemService:
    """Remote calls via gRPC."""
    def __init__(self, target: str):
        import grpc
        from . import items_pb2, items_pb2_grpc
        self._stub = items_pb2_grpc.ItemServiceStub(
            grpc.insecure_channel(target)
        )
    # ... methods translate Pydantic <-> protobuf wire

class HttpItemService:
    """Remote calls via HTTP (REST)."""
    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")
    # ... methods use httpx

def make_item_service() -> ItemServiceClient:
    """Factory: reads CRUD_MODE env var, returns the right impl."""
    mode = os.environ.get("CRUD_MODE", "embedded")
    if mode == "embedded":
        return EmbeddedItemService()
    elif mode == "grpc":
        return GrpcItemService(os.environ["CRUD_TARGET"])
    elif mode == "http":
        return HttpItemService(os.environ["CRUD_TARGET"])
    raise ValueError(f"Unknown CRUD_MODE: {mode}")
```

### FastAPI wiring

```python
# logic_app/deps.py
from functools import lru_cache
from generated.client import make_item_service, ItemServiceClient

@lru_cache
def get_item_service() -> ItemServiceClient:
    return make_item_service()

# logic_app/routes/items.py
from fastapi import APIRouter, Depends
from generated.models import Item, CreateItemRequest
from deps import get_item_service

router = APIRouter(prefix="/api/items")

@router.get("/", response_model=list[Item])
def list_items(svc = Depends(get_item_service)):
    return svc.list()

@router.post("/", response_model=Item, status_code=201)
def create_item(req: CreateItemRequest, svc = Depends(get_item_service)):
    return svc.create(req)
```

### Environment configuration

```bash
# .env (wrapper-shared)
CRUD_MODE=embedded           # "embedded" | "grpc" | "http"
CRUD_TARGET=localhost:50051  # only used when CRUD_MODE != embedded
DATABASE_URL=sqlite:///_shared/db.sqlite3
JWT_SECRET=...
```

## 4. Codegen Pipeline

One `make` target drives everything:

```
make gen-schema
  │
  ├─ 1. cargo build -p common_db
  │     (build.rs runs prost_build)
  │     proto/*.proto → common_db/src/proto_gen/*.rs
  │
  ├─ 2. python codegen/proto_to_pydantic.py proto/*.proto
  │     → logic_app/generated/models.py
  │
  └─ 3. python codegen/proto_to_client.py proto/*.proto
        → logic_app/generated/client.py
```

Steps 2 and 3 use Google's `protoc --descriptor_set_out` to parse the
proto into a `FileDescriptorSet`, then a Python script walks the
descriptor and emits Pydantic classes / client stubs via Jinja2 templates.
Total codegen: ~250 lines of Python + 2 Jinja2 templates.

### Template for Pydantic model generation (sketch)

```jinja2
{# codegen/templates/models.py.j2 #}
# AUTO-GENERATED from {{ source_file }} — do not edit

from pydantic import BaseModel
from typing import Optional

{% for msg in messages %}
class {{ msg.name }}(BaseModel):
{% for field in msg.fields %}
    {{ field.py_name }}: {{ field.py_type }}{% if field.optional %} = None{% endif %}

{% endfor %}
{% endfor %}
```

## 5. Migration Workflow (Schema Changes)

When the data model evolves:

1. **Edit** `proto/items.proto` — add field, new message, new RPC
2. **Write Diesel migration** — `diesel migration generate add_foo`
3. **Run** `make gen-schema` — regenerates:
   - Rust prost types (via `build.rs`)
   - Python Pydantic models + client stubs
4. **Run** `diesel migration run` — applies the SQL
5. **Update** `repo.rs` — add the new field to `From` conversions
6. **Compile** — Rust compiler catches missing fields in conversions;
   Python import errors catch Pydantic model mismatches

Drift is impossible: if the proto has a field that the Rust conversion
doesn't handle, `cargo build` fails. If the generated Pydantic model has
a field the client doesn't pass, FastAPI returns a validation error.

## 6. Skeleton Integration (dev_skel conventions)

The new `rust-hybrid-skel` follows standard dev_skel patterns:

| Convention | Implementation |
|-----------|---------------|
| `gen` script | Scaffolds workspace, runs `make gen-schema`, creates venvs |
| `merge` script | rsync overlay for re-runs |
| `test` script | Runs Rust tests (`cargo test`) + Python tests (`pytest`) |
| `deps` script | Installs Rust toolchain + `maturin` + Python deps |
| `install-deps` | Delegates to `deps`; installs `common_db` into Python venv via `maturin develop` |
| `VERSION` + `CHANGELOG.md` | Standard semver + Keep-a-Changelog |
| Wrapper `.env` | `DATABASE_URL`, `JWT_*`, `CRUD_MODE`, `CRUD_TARGET` |
| AI manifest | `_skels/_common/manifests/rust-hybrid-skel.py` |
| `./ai` + `./backport` | Installed by `common-wrapper.sh` as usual |

### Build command for local dev

```bash
# Install Rust extension into Python venv (embedded mode)
maturin develop -m common_db/Cargo.toml

# Or build for production
maturin build --release -m common_db/Cargo.toml
pip install target/wheels/common_db-*.whl
```

## 7. Testing Strategy

| Layer | Tool | What it tests |
|-------|------|---------------|
| Proto validity | `protoc --lint` | Schema well-formedness |
| Rust repo | `cargo test` in `common_db` | Diesel <-> Prost conversions, CRUD against test SQLite |
| Rust gateway | `cargo test` in `web_gateway` | HTTP + gRPC endpoint integration |
| Python models | `pytest` import check | Generated Pydantic models parse/serialize correctly |
| Embedded mode | `pytest` with `common_db` imported | Full round-trip: Python -> PyO3 -> Diesel -> SQLite -> back |
| gRPC mode | `pytest` with Tonic server running | Full round-trip over real gRPC |
| HTTP mode | `pytest` with Actix server running | Full round-trip over real HTTP |
| Cross-stack | `_bin/skel-test-*` harness | Wrapper-level end-to-end (register -> login -> CRUD) |

## 8. Dependency Summary

### Rust crates

| Crate | Purpose |
|-------|---------|
| `prost` + `prost-build` | Proto -> Rust struct codegen |
| `tonic` + `tonic-build` | gRPC server + client |
| `diesel` | ORM + migrations |
| `pyo3` | Python extension module |
| `pythonize` | serde <-> Python dict conversion |
| `actix-web` | HTTP server |
| `serde` + `serde_json` | JSON serialization |
| `chrono` | Timestamp handling |

### Python packages

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | Web framework + ASGI server |
| `pydantic` V2 | Validation + serialization |
| `maturin` | Build PyO3 extensions |
| `grpcio` + `grpcio-tools` | gRPC client (remote mode) |
| `httpx` | HTTP client (remote mode) |
| `protobuf` | Proto descriptor parsing (codegen only) |
| `jinja2` | Codegen templates |
| `pytest` | Testing |

## 9. Out of Scope

- **GraphQL adapter** — described in the design doc but not needed for
  the initial skeleton. Can be added later as an additional gateway
  route that calls the same repo.
- **Connection pooling tuning** — Diesel defaults are fine for the
  skeleton. Production tuning is per-deployment.
- **TLS / mTLS for gRPC** — the skeleton ships insecure channels.
  Production deployments add TLS via configuration.
- **Async Diesel** — Diesel 2.x is sync. The PyO3 bridge uses
  `allow_threads` and the Actix handlers use `web::block` to avoid
  blocking the event loop. Async Diesel support can be adopted when
  it stabilizes.
