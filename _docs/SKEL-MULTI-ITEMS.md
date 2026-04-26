# Multi-Item Order Workflow -- Skeleton Pattern Guide

> **Audience:** Claude Code, Junie, and any LLM agent adding or modifying
> the order workflow across dev_skel skeletons.

## Overview

Every backend skeleton ships a **generic order workflow** alongside the
existing items/categories CRUD. The order workflow demonstrates
multi-entity domains with:

- **4 related tables** (catalog, orders, lines, addresses)
- **Status transitions** (draft -> pending -> approved|rejected)
- **Nested detail responses** (order with lines + address)
- **Cross-entity operations** (add line looks up price from catalog)

The reference implementation lives in
`_skels/python-fastapi-skel/app/wrapper_api/orders.py` +
`order_models.py`. Every other skeleton replicates the same API contract.

## Shared DDL (SQLite)

All backends create these tables in the wrapper-shared
`_shared/db.sqlite3`:

```sql
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price REAL NOT NULL,
    category TEXT DEFAULT '',
    available INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES wrapper_user(id),
    status TEXT DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now')),
    submitted_at TEXT,
    wait_minutes INTEGER,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
    quantity INTEGER DEFAULT 1,
    unit_price REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS order_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    phone TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
```

For **Postgres** replace `AUTOINCREMENT` with `GENERATED ALWAYS AS
IDENTITY`, `INTEGER` with `BIGINT` for FKs, and `REAL` with
`DOUBLE PRECISION`. For **H2** (Java tests) use the same Postgres
syntax.

## API Contract

All endpoints live under `/api/`. All except `GET /api/catalog` require
a JWT bearer token from the wrapper-shared auth flow.

### Catalog

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | /api/catalog | - | `[{id, name, description, price, category, available}]` |
| GET | /api/catalog/{id} | - | `{id, name, ...}` |
| POST | /api/catalog | `{name, price, category?, description?, available?}` | 201 `{id, ...}` |

### Orders

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | /api/orders | - | 201 `{id, user_id, status:"draft", created_at, ...}` |
| GET | /api/orders | - | `[{id, user_id, status, ...}]` (user's orders only) |
| GET | /api/orders/{id} | - | `{..., lines: [...], address: {...} or null}` |

### Order lines

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | /api/orders/{id}/lines | `{catalog_item_id, quantity}` | 201 `{id, catalog_item_id, quantity, unit_price}` |
| DELETE | /api/orders/{id}/lines/{line_id} | - | 200 |

The `unit_price` is looked up from `catalog_items.price` server-side.

### Order address

| Method | Path | Body | Response |
|--------|------|------|----------|
| PUT | /api/orders/{id}/address | `{street, city, zip_code, phone?, notes?}` | 200 |

Upsert: creates on first call, updates on subsequent calls.

### Status transitions

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | /api/orders/{id}/submit | - | 200 `{..., status:"pending"}` |
| POST | /api/orders/{id}/approve | `{wait_minutes, feedback}` | 200 `{..., status:"approved", wait_minutes, feedback}` |
| POST | /api/orders/{id}/reject | `{feedback}` | 200 `{..., status:"rejected", feedback}` |

Guards: submit requires `status == "draft"`, approve/reject require
`status == "pending"`. Wrong status returns 400.

## Per-Skeleton Implementation

### python-fastapi-skel (REFERENCE)

| File | What |
|------|------|
| `app/wrapper_api/order_models.py` | SQLModel tables + Pydantic schemas |
| `app/wrapper_api/orders.py` | FastAPI router (12 endpoints) |
| `app/wrapper_api/router.py` | `include_router(orders_router)` |
| `app/wrapper_api/db.py` | Add 4 tables to `create_all()` |

Pattern: direct `session.exec(select(...))` + `session.get()`.

### python-django-bolt-skel

| File | What |
|------|------|
| `app/models.py` | Add CatalogItem, Order, OrderLine, OrderAddress Django models |
| `app/api.py` | Add 12 BoltAPI endpoints |
| `app/tests/test_api.py` | Add order workflow tests |

Pattern: Django ORM.

### python-django-skel

| File | What |
|------|------|
| `app/models.py` | Add 4 Django models |
| `app/views.py` | Add DRF APIView classes |
| `myproject/urls.py` | Add URL patterns |
| `tests/test_views.py` | Add tests |

### python-flask-skel

| File | What |
|------|------|
| `app/models.py` | Add 4 SQLAlchemy models |
| `app/routes.py` | Add `orders_bp` blueprint |
| `app/__init__.py` | Register blueprint |

### java-spring-skel

| File | What |
|------|------|
| `config/SchemaInitializer.java` | Add 4 CREATE TABLE (3 dialects) |
| `controller/OrderController.java` | 12 endpoints with JdbcClient |
| `ApplicationTests.java` | Add tests |

### rust-actix-skel

| File | What |
|------|------|
| `src/db.rs` | Add 4 CREATE TABLE |
| `src/handlers/orders.rs` | 12 handlers with sqlx |
| `src/main.rs` | Route registration |

### rust-axum-skel

| File | What |
|------|------|
| `src/db.rs` | Add 4 CREATE TABLE |
| `src/handlers/orders.rs` | 12 handlers (Axum extractors) |
| `src/main.rs` | Router registration |

### go-skel

| File | What |
|------|------|
| `internal/db/db.go` | Add 4 CREATE TABLE |
| `internal/handlers/orders.go` | 12 handlers |
| `main.go` | Register routes |

### next-js-skel

| File | What |
|------|------|
| `src/lib/db.js` | Add 4 CREATE TABLE in initDb() |
| `src/app/api/catalog/route.js` | GET + POST |
| `src/app/api/catalog/[id]/route.js` | GET |
| `src/app/api/orders/route.js` | GET + POST |
| `src/app/api/orders/[id]/route.js` | GET (detail) |
| `src/app/api/orders/[id]/lines/route.js` | POST |
| `src/app/api/orders/[id]/lines/[lineId]/route.js` | DELETE |
| `src/app/api/orders/[id]/address/route.js` | PUT |
| `src/app/api/orders/[id]/submit/route.js` | POST |
| `src/app/api/orders/[id]/approve/route.js` | POST |
| `src/app/api/orders/[id]/reject/route.js` | POST |

## Cross-Stack Test

`_bin/_frontend_backend_lib.py` exports `exercise_orders_api(backend_url)`
which runs the 14-step order lifecycle:

1. Register + login (reuse existing test user)
2. Create 3 catalog items
3. List catalog (assert >= 3)
4. Create order draft (assert status=draft)
5. Add 2 lines
6. Set delivery address
7. Verify order detail (2 lines + address)
8. Update address
9. Submit (assert status=pending)
10. Approve with wait_minutes=25 + feedback
11. Second order: submit + reject with feedback
12. Anonymous access rejected (401)
13. Invalid token rejected (401)

Every `skel-test-react-*` runner calls this after the existing items
flow.

## Testing Checklist

After adding the order workflow to a skeleton:

- [ ] Server starts without errors
- [ ] POST /api/catalog creates a catalog item (201)
- [ ] POST /api/orders creates a draft order (201, status=draft)
- [ ] POST /api/orders/{id}/lines adds a line with correct unit_price
- [ ] GET /api/orders/{id} returns nested lines + address
- [ ] Status transitions work correctly
- [ ] Approve response includes wait_minutes and feedback
- [ ] Anonymous request to /api/orders returns 401
- [ ] Cross-stack test passes
