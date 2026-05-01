# Complex AI Generation Test Playbook: FastAPI + Flutter Pizzeria

> **Canonical reference for building and running the pizzeria ordering
> test.** This document is the single source of truth — `CLAUDE.md`
> section 6.2 and `AGENTS.md` point here.
>
> **Audience:** Claude Code, Junie, and any LLM agent tasked with
> implementing or running this test.

---

## 1. Purpose and Success Criteria

**Goal:** from AI prompts only (no hand-editing of generated output),
`dev_skel` generates a FastAPI + Flutter project that passes all tests
for the full pizzeria order lifecycle:

```
menu → menu positions → order → order positions → address →
confirmation → wait-time feedback
```

This test proves that the AI generation pipeline can produce a complete
domain-specific application from instructions alone — the prompts in the
manifests must be strong enough that the LLM replaces the generic
"items" CRUD with a fully functional pizzeria ordering flow.

**Success** means all nine criteria in [Section 11 (Definition of
Done)](#11-definition-of-done) are met.

---

## 2. Domain Model and API Contract

The generated app replaces the skeleton's generic `item` CRUD with these
domain entities (all persisted to the wrapper-shared SQLite via
`DATABASE_URL`):

| Entity | Description | Key fields |
|--------|-------------|------------|
| `MenuPosition` | What can be ordered (pizza, drink, etc.) | `id`, `name`, `description`, `price`, `category`, `available` |
| `Order` | A customer's order | `id`, `user_id`, `status` (draft→pending→approved\|rejected), `created_at`, `submitted_at` |
| `OrderPosition` | A menu position selected into an order | `id`, `order_id`, `menu_position_id`, `quantity`, `unit_price` |
| `OrderAddress` | Delivery address attached to an order | `id`, `order_id`, `street`, `city`, `zip_code`, `phone`, `notes` |

### Status transitions

```
draft ──submit──→ pending ──approve──→ approved (+ wait_minutes + feedback)
                           ──reject───→ rejected (+ feedback)
```

### Backend API endpoints (FastAPI, all under `/api/`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/menu` | List all menu positions |
| `GET` | `/api/menu/{id}` | Get one menu position |
| `POST` | `/api/menu` | Create menu position (admin) |
| `POST` | `/api/orders` | Create order draft |
| `GET` | `/api/orders` | List user's orders |
| `GET` | `/api/orders/{id}` | Get order with positions + address |
| `POST` | `/api/orders/{id}/positions` | Add position to order draft |
| `DELETE` | `/api/orders/{id}/positions/{pos_id}` | Remove position |
| `PUT` | `/api/orders/{id}/address` | Set or update delivery address |
| `POST` | `/api/orders/{id}/submit` | Submit order (draft→pending) |
| `POST` | `/api/orders/{id}/approve` | Approve + set `wait_minutes` + `feedback` |
| `POST` | `/api/orders/{id}/reject` | Reject + set `feedback` |
| `POST` | `/api/auth/register` | Register (wrapper-shared auth) |
| `POST` | `/api/auth/login` | Login → JWT (wrapper-shared auth) |

### Frontend screens (Flutter)

1. **Menu list** — browse available menu positions, filter by category.
2. **Order builder** — select positions, edit quantities, see subtotal.
3. **Address form** — add or update delivery address during checkout.
4. **Confirmation** — submit order, see `pending` status.
5. **Status screen** — poll/display approved/rejected + wait-time
   feedback from restaurant.

---

## 3. Implementation Scope (What Claude Code Must Build)

The generated output is NEVER hand-edited. All changes go into manifests,
skeleton templates, or test infrastructure.

### 3A. Manifest Prompt Engineering

The AI generation pipeline sends prompts to Ollama with context from the
skeleton's reference templates. The prompts must be strong enough that
the LLM replaces "items" with the pizzeria domain. Two manifests may
need verification (but likely not modification):

**FastAPI manifest** (`_skels/_common/manifests/python-fastapi-skel.py`):

The existing manifest generates `app/{service_slug}/` with models,
adapters, routes, and tests. For the pizzeria test, the `backend_extra`
prompt placeholder (`{backend_extra}`) carries the domain-specific
instructions. The manifest itself does NOT need to be changed for the
pizzeria case — the domain instructions come through the `backend_extra`
prompt at generation time. However, verify that:

- Phase 1 targets can produce **multiple model files** when the prompt
  asks for `MenuPosition`, `Order`, `OrderPosition`, `OrderAddress` — if
  the current target list only generates one `models.py`, it may need to
  be split into multiple targets or the prompt must instruct the LLM to
  put all models in one file.
- The `routes.py` target produces all CRUD + workflow endpoints (submit,
  approve, reject) in a single file, or the manifest adds extra route
  targets.
- The `tests/` target generates tests that cover the full order
  lifecycle, not just CRUD.

**If manifest changes are needed** (e.g., adding targets for separate
route groups or model files), edit the manifest, NOT the generated
output. Run `make test-ai-generators-dry` after every manifest edit.

**Flutter manifest** (`_skels/_common/manifests/flutter-skel.py`):

Same principle — the `frontend_extra` prompt placeholder carries the
domain instructions. Verify that:

- The 4 existing targets (`api/{items_plural}_client.dart`,
  `controllers/{items_plural}_controller.dart`,
  `screens/{item_name}_list.dart`, `screens/{item_name}_form.dart`) map
  to the pizzeria domain when `item_class=Order`, `item_name=order`,
  `items_plural=orders`.
- Additional screens (address form, status/confirmation) either fit into
  the existing target structure or require new targets.
- The `home_screen.dart` is NOT in the target list by design — if the
  navigation flow changes (menu → builder → address → confirmation →
  status), either the prompt must instruct the LLM to update
  screen-internal navigation, or `home_screen.dart` must be added as a
  target.

### 3B. Scripted Generation (Non-Interactive)

For automated testing, `skel-gen-ai` must be called with `--no-input`
and explicit flags so no interactive dialog is needed. The test script
invocation looks like:

```bash
_bin/skel-gen-ai \
    _test_projects/test-pizzeria-orders \
    --backend python-fastapi-skel \
    --frontend flutter-skel \
    --backend-service "Orders API" \
    --frontend-service "Pizzeria App" \
    --item-class Order \
    --auth-type jwt \
    --backend-extra "$(cat <<'PROMPT'
Replace generic item CRUD with a pizzeria ordering domain.
Entities: MenuPosition (name, description, price, category, available),
Order (user_id, status: draft/pending/approved/rejected, created_at, submitted_at),
OrderPosition (order_id, menu_position_id, quantity, unit_price),
OrderAddress (order_id, street, city, zip_code, phone, notes).
API: GET/POST /api/menu, POST /api/orders (create draft),
POST /api/orders/{id}/positions (add position), DELETE /api/orders/{id}/positions/{pos_id},
PUT /api/orders/{id}/address, POST /api/orders/{id}/submit (draft->pending),
POST /api/orders/{id}/approve (set wait_minutes + feedback),
POST /api/orders/{id}/reject (set feedback).
Status flow: draft -> pending -> approved|rejected.
Approve/reject must accept wait_minutes (int, minutes) and feedback (str).
Keep wrapper-shared auth (register/login -> JWT). Keep DATABASE_URL env-driven.
Generate tests covering: menu listing, order creation, position add/remove,
address set/update, submit, approve with wait_minutes, reject with feedback.
PROMPT
)" \
    --frontend-extra "$(cat <<'PROMPT'
Replace item screens with pizzeria ordering UX.
Screens: MenuList (browse menu positions, filter by category),
OrderBuilder (select positions, edit quantities, see subtotal),
AddressForm (add or update delivery address during checkout),
Confirmation (submit order, show pending status),
StatusScreen (show approved/rejected + wait_minutes + feedback from restaurant).
Navigation: menu list -> order builder -> address form -> confirmation -> status.
Use existing auth/token infrastructure. Read BACKEND_URL from AppConfig.
Generate tests for: menu rendering, position selection, address form,
order submission, status display with wait-time feedback.
PROMPT
)" \
    --integration-extra "$(cat <<'PROMPT'
Verify the full pizzeria flow end-to-end:
1) register user, 2) login, 3) list menu positions,
4) create order draft, 5) add positions from menu,
6) set delivery address, 7) submit order (status->pending),
8) approve order (set wait_minutes=25, feedback="Your pizza is being prepared"),
9) verify order status is approved with correct wait_minutes and feedback.
Also test reject path: create second order, submit, reject with feedback.
PROMPT
)" \
    --no-input
```

**Important:** if `skel-gen-ai` does not yet support all of these flags
in `--no-input` mode, the test script must implement the equivalent by:

1. Calling `_bin/skel-gen-static` first (creates the scaffold).
2. Then calling `_bin/skel-gen-ai --skip-base` with the prompts (runs
   only the AI overlay phases).

Check `_bin/skel-gen-ai --help` for the current flag set. The
`--backend-extra` / `--frontend-extra` / `--integration-extra` flags
should map to the `{backend_extra}` / `{frontend_extra}` /
`{integration_extra}` prompt placeholders in the manifests.

### 3C. Cross-Stack Integration Test Script

Create `_bin/skel-test-pizzeria-orders` following the pattern of
`_bin/skel-test-flutter-fastapi`. The script must:

1. **Generate** the wrapper under `_test_projects/test-pizzeria-orders`
   using the scripted invocation from (3B).
2. **Configure** `BACKEND_URL` to a non-conflicting port (e.g. 18790) in
   the wrapper `.env`.
3. **Install deps** via `./install-deps` in the wrapper.
4. **Run backend tests** (`./test orders_api`) — these are the
   AI-generated pytest tests inside the FastAPI service. They must cover
   the full order lifecycle.
5. **Run frontend tests** (`./test pizzeria_app`) — Flutter widget tests
   validating the screens and navigation.
6. **Start the FastAPI server** in the background on the configured port.
7. **Exercise the pizzeria API over real HTTP** (the core integration
   check — see [Section 4](#4-http-integration-test-flow)).
8. **Stop the server** and clean up (or keep with `--keep`).

The script uses `_bin/_frontend_backend_lib.py` helpers: `BackendSpec`,
`http_request`, `wait_for_server`, `update_wrapper_env`,
`generate_one_service`, `chdir`.

**New file:** `_bin/skel-test-pizzeria-orders` (executable, Python 3).

**Makefile targets** to add:

```makefile
test-pizzeria-orders: ## Full pizzeria generation + cross-stack integration test
	@_bin/skel-test-pizzeria-orders

test-pizzeria-orders-keep: ## Same, but leave _test_projects/ on disk
	@_bin/skel-test-pizzeria-orders --keep
```

---

## 4. HTTP Integration Test Flow

After the server is up on `http://localhost:{port}`, the script runs this
sequence using `http_request()` from `_frontend_backend_lib`:

```python
# ── Step 1: Register ──
status, body = http_request("POST", f"{base}/api/auth/register", body={
    "username": "pizzeria-test-user",
    "password": "test-password-12345",
    "email": "pizza@example.com",
})
assert status in (200, 201), f"register failed: {status} {body}"

# ── Step 2: Login ──
status, body = http_request("POST", f"{base}/api/auth/login", body={
    "username": "pizzeria-test-user",
    "password": "test-password-12345",
})
assert status == 200
token = body["access_token"]  # or body["token"]
auth = {"Authorization": f"Bearer {token}"}

# ── Step 3: Seed menu positions ──
for item in [
    {"name": "Margherita", "price": 12.50, "category": "pizza"},
    {"name": "Pepperoni", "price": 14.00, "category": "pizza"},
    {"name": "Cola", "price": 3.50, "category": "drink"},
]:
    status, _ = http_request("POST", f"{base}/api/menu", body=item, headers=auth)
    assert status in (200, 201), f"create menu position failed: {status}"

# ── Step 4: List menu ──
status, menu = http_request("GET", f"{base}/api/menu", headers=auth)
assert status == 200
assert len(menu) >= 3, f"expected >=3 menu positions, got {len(menu)}"

# ── Step 5: Create order draft ──
status, order = http_request("POST", f"{base}/api/orders", body={}, headers=auth)
assert status in (200, 201)
order_id = order["id"]
assert order["status"] == "draft"

# ── Step 6: Add positions to order ──
margherita_id = next(m["id"] for m in menu if m["name"] == "Margherita")
cola_id = next(m["id"] for m in menu if m["name"] == "Cola")

status, _ = http_request("POST", f"{base}/api/orders/{order_id}/positions", body={
    "menu_position_id": margherita_id, "quantity": 2,
}, headers=auth)
assert status in (200, 201)

status, _ = http_request("POST", f"{base}/api/orders/{order_id}/positions", body={
    "menu_position_id": cola_id, "quantity": 1,
}, headers=auth)
assert status in (200, 201)

# ── Step 7: Set delivery address ──
status, _ = http_request("PUT", f"{base}/api/orders/{order_id}/address", body={
    "street": "ul. Marszałkowska 1",
    "city": "Warszawa",
    "zip_code": "00-001",
    "phone": "+48 123 456 789",
    "notes": "Ring twice",
}, headers=auth)
assert status in (200, 201)

# ── Step 8: Verify order has positions + address ──
status, full_order = http_request("GET", f"{base}/api/orders/{order_id}", headers=auth)
assert status == 200
assert len(full_order.get("positions", [])) == 2
assert full_order.get("address") is not None
assert full_order["address"]["city"] == "Warszawa"

# ── Step 9: Update address ──
status, _ = http_request("PUT", f"{base}/api/orders/{order_id}/address", body={
    "street": "ul. Nowy Świat 15",
    "city": "Warszawa",
    "zip_code": "00-029",
    "phone": "+48 987 654 321",
}, headers=auth)
assert status in (200, 201)

# ── Step 10: Submit order ──
status, submitted = http_request(
    "POST", f"{base}/api/orders/{order_id}/submit", body={}, headers=auth,
)
assert status == 200
assert submitted["status"] == "pending"

# ── Step 11: Approve order with wait time + feedback ──
status, approved = http_request(
    "POST", f"{base}/api/orders/{order_id}/approve", body={
        "wait_minutes": 25,
        "feedback": "Your pizza is being prepared!",
    }, headers=auth,
)
assert status == 200
assert approved["status"] == "approved"
assert approved["wait_minutes"] == 25
assert "pizza" in approved["feedback"].lower()

# ── Step 12: Create second order → reject path ──
status, order2 = http_request("POST", f"{base}/api/orders", body={}, headers=auth)
order2_id = order2["id"]
# add a position, set address, submit
http_request("POST", f"{base}/api/orders/{order2_id}/positions", body={
    "menu_position_id": margherita_id, "quantity": 1,
}, headers=auth)
http_request("PUT", f"{base}/api/orders/{order2_id}/address", body={
    "street": "ul. Krakowskie Przedmieście 5", "city": "Warszawa",
    "zip_code": "00-068",
}, headers=auth)
http_request("POST", f"{base}/api/orders/{order2_id}/submit", body={}, headers=auth)

status, rejected = http_request(
    "POST", f"{base}/api/orders/{order2_id}/reject", body={
        "feedback": "Sorry, we are closed for today.",
    }, headers=auth,
)
assert status == 200
assert rejected["status"] == "rejected"
assert "closed" in rejected["feedback"].lower()

# ── Step 13: Reject anonymous access ──
status, _ = http_request("GET", f"{base}/api/orders")
assert status in (401, 403)

# ── Step 14: Reject invalid token ──
status, _ = http_request("GET", f"{base}/api/orders", headers={
    "Authorization": "Bearer invalid-token-xyz",
})
assert status in (401, 403)
```

Each assertion failure should print the step name, expected vs actual,
and the raw response body for debugging. The script should report a
summary at the end (14/14 passed, or which steps failed).

---

## 5. Backend Test Expectations (AI-Generated pytest)

The AI-generated `app/orders_api/tests/` inside the FastAPI service must
include tests that cover (at minimum):

### Model layer tests

- `MenuPosition` CRUD (create, list, get by id).
- `Order` creation returns draft status.
- `OrderPosition` links order to menu position with quantity.
- `OrderAddress` stores delivery details on an order.

### Route/API tests (using FastAPI `TestClient`)

- `GET /api/menu` returns list of menu positions.
- `POST /api/menu` creates a menu position (authenticated).
- `POST /api/orders` creates a draft order (authenticated).
- `POST /api/orders/{id}/positions` adds position to draft.
- `DELETE /api/orders/{id}/positions/{pos_id}` removes position.
- `PUT /api/orders/{id}/address` sets/updates delivery address.
- `POST /api/orders/{id}/submit` transitions draft → pending.
- `POST /api/orders/{id}/submit` on non-draft → 400/409.
- `POST /api/orders/{id}/approve` transitions pending → approved,
  stores `wait_minutes` and `feedback`.
- `POST /api/orders/{id}/reject` transitions pending → rejected,
  stores `feedback`.
- `POST /api/orders/{id}/approve` on non-pending → 400/409.

### Auth tests

- Anonymous requests to protected endpoints → 401.
- Invalid token → 401.
- Valid token from wrapper-shared JWT config → 200.

These tests should run via `pytest` from the service directory (`./test`
or `cd orders_api && python -m pytest`). They should use the FastAPI
`TestClient` (no live server needed) and an in-memory or temp SQLite
database.

---

## 6. Frontend Test Expectations (AI-Generated Flutter tests)

The AI-generated `test/` inside the Flutter service must include:

### Widget tests

- Menu list screen renders menu position names.
- Order builder screen allows selecting positions and editing quantities.
- Address form screen has fields for street, city, zip, phone.
- Confirmation screen shows order summary and pending status.
- Status screen shows approved/rejected with wait-time feedback.

### Controller tests

- Orders controller creates a draft order.
- Orders controller adds/removes positions.
- Orders controller submits order.
- Address controller saves/updates address.

### Integration tests (config/client construction only — no live HTTP)

- `AppConfig` loads `BACKEND_URL` from the wrapper `.env`.
- API client constructors do not throw.
- Sibling URL is available in config when a backend is present.

These tests should run via `flutter test` from the service directory.
They use `flutter_test` mocking — no live backend needed.

---

## 7. Operator Workflow (Step-by-Step)

Follow these steps **in order**. Each step must pass before proceeding to
the next. All test artifacts go under `_test_projects/`.

### Phase 0: Pre-flight checks

```bash
# Point at the Ollama host. A bare hostname is fine — the resolver
# defaults the port to 11434 (see _docs/MODELS.md).
export OLLAMA_HOST=paul   # or localhost / your remote box

# Verify all five per-phase models are pulled (gen/create_test/
# check_test/fix/docs). Defaults live in `_bin/skel_rag/config.py`.
curl -sf "http://${OLLAMA_HOST}:11434/api/tags" | python3 -c \
  "import json, sys; \
   names = {m['name'] for m in json.load(sys.stdin).get('models', [])}; \
   need = ['qwen3-coder:30b', 'devstral:latest', 'qwq:32b', \
           'qwen2.5-coder:32b', 'qwen2.5:7b-instruct']; \
   missing = [n for n in need if n not in names]; \
   print('missing:' if missing else 'all 5 present.', missing or '')"

# Verify Flutter toolchain
flutter --version
flutter doctor --android-licenses 2>/dev/null || true

# Verify Python + FastAPI deps
python3 -c "import fastapi, sqlmodel, uvicorn; print('FastAPI deps OK')"

# Dry-run to confirm manifests load
make test-ai-generators-dry
```

### Phase 1: Generate the project

```bash
# Clean any previous run
rm -rf _test_projects/test-pizzeria-orders

# Generate with AI (this takes 10-30 minutes depending on hardware)
_bin/skel-gen-ai \
    _test_projects/test-pizzeria-orders \
    --backend python-fastapi-skel \
    --frontend flutter-skel \
    --backend-service "Orders API" \
    --frontend-service "Pizzeria App" \
    --item-class Order \
    --auth-type jwt \
    --backend-extra "<PIZZERIA_BACKEND_PROMPT>" \
    --frontend-extra "<PIZZERIA_FRONTEND_PROMPT>" \
    --integration-extra "<PIZZERIA_INTEGRATION_PROMPT>" \
    --no-input
```

(Replace `<PIZZERIA_*_PROMPT>` with the prompts from [Section
3B](#3b-scripted-generation-non-interactive).)

### Phase 2: Install deps + run service tests

```bash
cd _test_projects/test-pizzeria-orders

# Install all service dependencies
./install-deps

# Run backend tests first (most likely to fail on domain generation)
./test orders_api
# Expected: pytest passes with all order lifecycle tests green

# Run frontend tests
./test pizzeria_app
# Expected: flutter test passes with widget + controller tests green

# Run all tests (both services)
./test
```

### Phase 3: Cross-stack HTTP integration

Either run the dedicated script:

```bash
# From repo root
_bin/skel-test-pizzeria-orders --keep
```

Or manually:

```bash
cd _test_projects/test-pizzeria-orders

# Update BACKEND_URL to the test port
# (the script does this automatically)
sed -i '' 's|BACKEND_URL=.*|BACKEND_URL=http://localhost:18790|' .env

# Start backend
cd orders_api
python -m uvicorn main:app --host 127.0.0.1 --port 18790 &
SERVER_PID=$!
cd ..

# Wait for server
until curl -sf http://localhost:18790/api/health; do sleep 0.5; done

# Run the HTTP integration flow (steps 1-14 from Section 4)
# ...

# Cleanup
kill $SERVER_PID
```

### Phase 4: Fix-loop (if any test fails)

```
┌──────────────────────────────────────────────────────────────┐
│  Test failure?                                               │
│  │                                                           │
│  ├─ Backend test fails on domain logic                       │
│  │  → Fix the backend_extra prompt in the manifest or in     │
│  │    the test script invocation. Regenerate. Do NOT         │
│  │    hand-edit the generated `orders_api/` code.            │
│  │                                                           │
│  ├─ Backend test fails on auth/DB                            │
│  │  → Check wrapper .env (JWT_SECRET, DATABASE_URL).         │
│  │    Check core/config.py reads wrapper env correctly.      │
│  │    This is a skeleton bug — fix in _skels/                │
│  │    python-fastapi-skel/, then regenerate.                 │
│  │                                                           │
│  ├─ Frontend test fails                                      │
│  │  → Fix the frontend_extra prompt. Check that              │
│  │    lib/config.dart and lib/auth/ are not being            │
│  │    overwritten by the manifest (they shouldn't be).       │
│  │    Regenerate.                                            │
│  │                                                           │
│  ├─ HTTP integration fails on specific step                  │
│  │  → The API contract doesn't match expectations.           │
│  │    Tighten the backend_extra prompt to be more            │
│  │    explicit about the endpoint path/method/response       │
│  │    shape. Regenerate and re-test.                         │
│  │                                                           │
│  └─ Flutter build fails                                      │
│     → Check `flutter analyze` output. Common issues:         │
│       Category name collision with flutter/foundation.dart   │
│       (use ItemCategory), missing imports, Dart style.       │
│       Fix the prompt to be more specific about naming.       │
│       Regenerate.                                            │
│                                                              │
│  After every fix: delete _test_projects/test-pizzeria-orders │
│  and regenerate from scratch. Run the failing test first,    │
│  then the full suite.                                        │
└──────────────────────────────────────────────────────────────┘
```

### Phase 5: Validate generator infrastructure

After the pizzeria test passes, confirm nothing else broke:

```bash
# From repo root
make test-ai-generators-dry         # always cheap, must pass
make test-generators                 # static skeleton tests
make test-flutter-fastapi            # existing cross-stack test
# If Ollama is available:
make test-ai-generators              # full AI pipeline (~30+ min)
```

---

## 8. Test Matrix (Complete Checklist)

Run tests in this order — changed scope first, then broader suites.

### Tier 1: Generated service tests (inside wrapper)

- [ ] `./test orders_api` — backend pytest suite:
  - [ ] Menu position CRUD (list, create, get).
  - [ ] Order draft creation.
  - [ ] Order position add/remove with validation.
  - [ ] Address set/update on order.
  - [ ] Submit (draft → pending).
  - [ ] Approve with wait_minutes + feedback (pending → approved).
  - [ ] Reject with feedback (pending → rejected).
  - [ ] Invalid transitions return 400/409.
  - [ ] Auth: anonymous → 401, invalid token → 401.
- [ ] `./test pizzeria_app` — frontend Flutter tests:
  - [ ] Menu list screen renders positions.
  - [ ] Order builder supports position selection + quantity.
  - [ ] Address form has all required fields.
  - [ ] Confirmation screen shows pending.
  - [ ] Status screen shows approved/rejected + wait feedback.
- [ ] `./test` — both services together.

### Tier 2: Cross-stack HTTP integration

- [ ] `_bin/skel-test-pizzeria-orders` (or `make test-pizzeria-orders`):
  - [ ] Steps 1-2: register + login → JWT token.
  - [ ] Steps 3-4: seed menu positions + list them.
  - [ ] Steps 5-6: create order draft + add positions.
  - [ ] Steps 7-9: set address, verify, update address.
  - [ ] Step 10: submit order (draft → pending).
  - [ ] Step 11: approve order with wait_minutes + feedback.
  - [ ] Step 12: second order → reject path.
  - [ ] Steps 13-14: reject anonymous + invalid token.

### Tier 3: Repository-level regression

- [ ] `make test-ai-generators-dry` — manifest dispatch is intact.
- [ ] `make test-generators` — all static skeleton tests pass.
- [ ] `make test-flutter-fastapi` — existing generic cross-stack test
  still passes (the pizzeria changes must not break the default items
  flow).
- [ ] `make test-ai-generators` — full AI pipeline (if Ollama available;
  ~30+ min).

---

## 9. File Inventory

### New files

| Path | Purpose |
|------|---------|
| `_docs/PIZZERIA-TEST-PLAYBOOK.md` | This document |
| `_bin/skel-test-pizzeria-orders` | Cross-stack integration test script (executable Python 3) |

### Modified files (potential)

| Path | Change |
|------|--------|
| `Makefile` | Add `test-pizzeria-orders` / `test-pizzeria-orders-keep` targets |
| `_skels/_common/manifests/python-fastapi-skel.py` | Only if the current target list can't express the domain (e.g., needs extra route groups) |
| `_skels/_common/manifests/flutter-skel.py` | Only if extra screens need extra targets |
| `CLAUDE.md` | Short pointer to this document in section 6.2 |
| `AGENTS.md` | Short pointer to this document |

### Generated files (under `_test_projects/`, NEVER committed)

```
_test_projects/test-pizzeria-orders/
├── .env                         # wrapper-shared env
├── _shared/db.sqlite3           # shared database
├── orders_api/                  # FastAPI service (AI-generated)
│   ├── app/
│   │   ├── orders_api/          # domain module
│   │   │   ├── models.py        # MenuPosition, Order, OrderPosition, OrderAddress
│   │   │   ├── adapters/sql.py  # SQLModel persistence
│   │   │   ├── routes.py        # all API endpoints
│   │   │   ├── depts.py         # FastAPI dependencies
│   │   │   └── tests/           # pytest tests
│   │   ├── integrations/        # Phase 3 cross-service code
│   │   └── wrapper_api/         # shared auth/items/state
│   ├── core/                    # shared domain (auth, config, security)
│   └── tests/
├── pizzeria_app/                # Flutter service (AI-generated)
│   ├── lib/
│   │   ├── api/orders_client.dart
│   │   ├── controllers/orders_controller.dart
│   │   ├── screens/
│   │   │   ├── order_list.dart  # or menu_list.dart
│   │   │   ├── order_form.dart  # or order_builder.dart
│   │   │   └── home_screen.dart
│   │   ├── auth/                # wrapper-shared (not regenerated)
│   │   ├── config.dart          # wrapper-shared (not regenerated)
│   │   └── state/               # wrapper-shared (not regenerated)
│   └── test/
├── run, test, build, stop, install-deps  # wrapper dispatch scripts
└── services                     # service discovery
```

---

## 10. Prompt Tuning Guidelines

If the LLM produces output that doesn't match the expected API contract,
iterate on the prompts using these principles:

1. **Be explicit about paths and methods.** Don't say "add order
   endpoints" — say `POST /api/orders/{id}/approve accepts JSON body
   {wait_minutes: int, feedback: str} and returns the updated order with
   status='approved'`.

2. **Name the response shape.** If you expect `{"status": "approved",
   "wait_minutes": 25, "feedback": "..."}`, say so in the prompt. The
   LLM may otherwise nest it under `data` or `result`.

3. **Anchor to the reference template.** The prompt should say "follow
   the same patterns as `app/example_items/`" so the LLM inherits the
   existing DDD layering (models → adapters → depts → routes).

4. **One entity per model file vs. all-in-one.** The default FastAPI
   manifest generates one `models.py`. If 4 entities in one file produces
   unstable output, consider splitting the manifest into
   `models/menu.py`, `models/order.py`, etc. — but try the single-file
   approach first (simpler manifest).

5. **Test the prompt incrementally.** Before running the full generation:

   ```bash
   # Generate backend only, skip frontend + integration
   _bin/skel-gen-ai _test_projects/test-pizzeria-backend-only \
       python-fastapi-skel "Orders API" \
       --item-class Order --auth-type jwt \
       --backend-extra "..." \
       --no-input --no-integrate --no-test-fix
   ```

   Inspect the generated files. If the models/routes look wrong, fix the
   prompt and regenerate. Only proceed to full-stack once the backend
   output is stable.

6. **Frontend prompts depend on backend output.** The Flutter
   `frontend_extra` prompt should reference the exact API paths from the
   backend. If the backend generates `/api/menu-positions` instead of
   `/api/menu`, the frontend prompt must match.

---

## 11. Definition of Done

The scenario is complete only when ALL of these are true:

1. A FastAPI + Flutter project is generated from `_skels/` with AI
   prompts only (zero hand-edits in `_test_projects/`).
2. `./test orders_api` passes — backend covers the full order lifecycle
   (menu → positions → address → submit → approve/reject).
   *Caveat:* the AI-generated `tests/test_cross_stack_integration.py`
   sometimes ships content-quality bugs (assertion mismatches between
   the test and the just-generated implementation). Wiring the new
   `CHECK_TEST` slot (`qwq:32b`, see `_docs/MODELS.md`) into
   `run_test_generation_phase` is the planned remediation.
3. `./test pizzeria_app` passes — frontend screens render correctly.
   *Caveat:* the runner already removes the two stale skel test files
   that hard-code `ItemForm` / `ItemsController` (see
   `_run_frontend_tests` in `_bin/skel-test-pizzeria-orders`); deeper
   AI naming inconsistencies between `home_screen.dart` /
   `order_list.dart` / generated controllers are again the
   `CHECK_TEST` slot's job.
4. `_bin/skel-test-pizzeria-orders` passes — all 14 HTTP integration
   steps green twice (once after backend+React generation, once after
   Flutter add). This is the canonical infra-level pass marker; the
   runner emits `=== ALL CHECKS PASSED ===` and exits 0 when both
   integration sweeps succeed, even if the AI-content unit tests
   above hit caveats.
5. `make test-ai-generators-dry` passes — manifest dispatch intact.
6. `make test-generators` passes — no regressions in other skeletons.
7. `make test-flutter-fastapi` passes — the generic items flow is
   unbroken.
8. The test script (`_bin/skel-test-pizzeria-orders`) and Makefile
   targets are committed and documented.
9. This document and the pointers in `CLAUDE.md` / `AGENTS.md`
   accurately describe the final implementation.
