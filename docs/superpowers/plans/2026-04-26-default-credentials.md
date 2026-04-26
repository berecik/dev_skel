# Default Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add default user/superuser accounts that are auto-seeded at startup, with login-by-email-or-username support across all 9 backend skeletons.

**Architecture:** Six new env vars in the shared `.env` template. Each backend's existing startup/schema-init path gets an idempotent seed step. Each backend's login handler gets email-or-username lookup via `@` detection. Cross-stack test lib gets `check_seeded_accounts()`.

**Tech Stack:** Python (Django/FastAPI/Flask), Java (Spring Boot), Rust (Actix/Axum), Go, Node.js (Next.js)

**Spec:** `docs/superpowers/specs/2026-04-25-default-credentials-design.md`

---

## File Map

### Shared infrastructure
| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `_skels/_common/common-wrapper.sh` | Add 6 env vars to `.env.example` heredoc |
| Modify | `_bin/_frontend_backend_lib.py` | Add `check_seeded_accounts()` |
| Modify | `README.md` | Document new env vars |
| Modify | `_docs/DEPENDENCIES.md` | Document new env vars |
| Modify | `_docs/LLM-MAINTENANCE.md` | Mention seeding behavior |

### Per-skeleton (seed + login-by-email + tests)
| Skeleton | Seed location | Login file | Test file |
|----------|--------------|------------|-----------|
| python-django-bolt-skel | `app/seed.py` (new) + `app/settings.py` | `app/services/auth_service.py` | `app/tests/test_api.py` |
| python-django-skel | `app/seed.py` (new) + `myproject/settings.py` | `app/views.py` | `tests/test_views.py` |
| python-fastapi-skel | `app/wrapper_api/seed.py` (new) + startup lifespan | `app/wrapper_api/auth.py` | existing test file |
| python-flask-skel | `app/seed.py` (new) + `app/__init__.py` | `app/routes.py` | existing test file |
| java-spring-skel | `config/SchemaInitializer.java` | `controller/AuthController.java` | `ApplicationTests.java` |
| rust-actix-skel | `src/seed.rs` (new) + `src/main.rs` | `src/handlers/auth.rs` | integration test |
| rust-axum-skel | `src/seed.rs` (new) + `src/main.rs` | `src/handlers/auth.rs` | integration test |
| go-skel | `internal/seed/seed.go` (new) + `cmd/server/main.go` | `internal/handlers/handlers.go` | test file |
| next-js-skel | `src/lib/seed.js` (new) + server init | `src/app/api/auth/login/route.js` | existing test |

---

## Task 1: Shared `.env` template

**Files:**
- Modify: `_skels/_common/common-wrapper.sh:142-149`

- [ ] **Step 1: Add env vars to the `.env.example` heredoc**

In `_skels/_common/common-wrapper.sh`, before the `EOF` line (currently line 149), add:

```bash
# ----- Default accounts (seeded on first startup) ------------------------- #
# Every backend creates these accounts at startup if they don't exist.
# Change passwords before deploying to production.
USER_LOGIN=user
USER_EMAIL=user@example.com
USER_PASSWORD=secret
SUPERUSER_LOGIN=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=secret
```

- [ ] **Step 2: Verify the template renders**

Generate a throwaway project, check the .env contains USER_LOGIN=user, then clean up.

- [ ] **Step 3: Commit**

---

## Task 2: python-django-bolt-skel (seed + login-by-email)

**Files:**
- Create: `_skels/python-django-bolt-skel/app/seed.py`
- Modify: `_skels/python-django-bolt-skel/app/settings.py`
- Modify: `_skels/python-django-bolt-skel/app/services/auth_service.py`
- Modify: `_skels/python-django-bolt-skel/app/tests/test_api.py`

- [ ] **Step 1: Create `app/seed.py`**

```python
"""Seed default user accounts from env vars on startup."""

import logging
import os

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def seed_default_accounts() -> None:
    """Create USER_LOGIN and SUPERUSER_LOGIN if they don't exist."""
    User = get_user_model()
    accounts = [
        {
            "username": os.environ.get("USER_LOGIN", "user"),
            "email": os.environ.get("USER_EMAIL", "user@example.com"),
            "password": os.environ.get("USER_PASSWORD", "secret"),
            "is_superuser": False,
        },
        {
            "username": os.environ.get("SUPERUSER_LOGIN", "admin"),
            "email": os.environ.get("SUPERUSER_EMAIL", "admin@example.com"),
            "password": os.environ.get("SUPERUSER_PASSWORD", "secret"),
            "is_superuser": True,
        },
    ]
    for acct in accounts:
        username = acct["username"]
        if User.objects.filter(username=username).exists():
            logger.info("[seed] Default user '%s' already exists", username)
            continue
        user = User.objects.create_user(
            username=username,
            email=acct["email"],
            password=acct["password"],
        )
        user.is_superuser = acct["is_superuser"]
        user.is_staff = acct["is_superuser"]
        user.save(update_fields=["is_superuser", "is_staff"])
        logger.info("[seed] Created default user '%s'", username)
```

- [ ] **Step 2: Call seed from settings.py startup**

Append at end of `app/settings.py` — deferred seed call with try/except so it does not crash on first `manage.py migrate` when tables don't exist yet.

- [ ] **Step 3: Update `authenticate_user` for email-or-username login**

In `app/services/auth_service.py`, modify `authenticate_user` to check `"@" in username` and query by email or username accordingly:

```python
@staticmethod
def authenticate_user(username: str, password: str):
    User = get_user_model()
    try:
        if "@" in username:
            user = User.objects.get(email=username)
        else:
            user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None
    if not user.check_password(password):
        return None
    tokens = AuthService.get_tokens_for_user(user)
    return {**tokens, "user_id": user.id, "username": user.username}
```

- [ ] **Step 4: Add tests to `app/tests/test_api.py`**

```python
def test_default_user_can_login(self):
    resp = self.client.post("/api/auth/login",
        {"username": "user", "password": "secret"},
        content_type="application/json")
    self.assertEqual(resp.status_code, 200)
    data = resp.json()
    self.assertIn("access", data)
    token = data["access"]
    items_resp = self.client.get("/api/items",
        HTTP_AUTHORIZATION=f"Bearer {token}")
    self.assertEqual(items_resp.status_code, 200)

def test_default_superuser_can_login(self):
    resp = self.client.post("/api/auth/login",
        {"username": "admin", "password": "secret"},
        content_type="application/json")
    self.assertEqual(resp.status_code, 200)
    self.assertIn("access", resp.json())

def test_login_by_email(self):
    resp = self.client.post("/api/auth/login",
        {"username": "user@example.com", "password": "secret"},
        content_type="application/json")
    self.assertEqual(resp.status_code, 200)
    self.assertIn("access", resp.json())

def test_login_by_email_superuser(self):
    resp = self.client.post("/api/auth/login",
        {"username": "admin@example.com", "password": "secret"},
        content_type="application/json")
    self.assertEqual(resp.status_code, 200)
    self.assertIn("access", resp.json())
```

- [ ] **Step 5: Run tests**
- [ ] **Step 6: Commit**

---

## Task 3: python-django-skel (seed + login-by-email)

**Files:**
- Create: `_skels/python-django-skel/app/seed.py`
- Modify: `_skels/python-django-skel/myproject/settings.py`
- Modify: `_skels/python-django-skel/app/views.py`
- Modify: `_skels/python-django-skel/tests/test_views.py`

- [ ] **Step 1: Create `app/seed.py`** — same Django ORM logic as Task 2 Step 1

- [ ] **Step 2: Call seed from `myproject/settings.py`** — same deferred pattern as Task 2 Step 2

- [ ] **Step 3: Update `LoginView` for email-or-username**

In `app/views.py`, modify `LoginView.post()` — if `"@" in username`, look up the User by email first, then call `authenticate()` with their actual username:

```python
if "@" in username:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user_obj = User.objects.get(email=username)
    except User.DoesNotExist:
        return _unauth("invalid username or password")
    user = authenticate(request, username=user_obj.username, password=password)
else:
    user = authenticate(request, username=username, password=password)
```

- [ ] **Step 4: Add 4 tests** — same pattern as Task 2 Step 4, adapted for DRF test client
- [ ] **Step 5: Run tests, commit**

---

## Task 4: python-fastapi-skel (seed + login-by-email)

**Files:**
- Create: `_skels/python-fastapi-skel/app/wrapper_api/seed.py`
- Modify: `_skels/python-fastapi-skel/app/wrapper_api/auth.py`
- Modify: FastAPI lifespan/startup (app creation point)

- [ ] **Step 1: Create `app/wrapper_api/seed.py`**

Uses SQLModel session, `hash_password()` from security module. Same account list pattern. Inserts `WrapperUser` objects.

- [ ] **Step 2: Call seed from FastAPI lifespan startup** — after engine/session setup

- [ ] **Step 3: Update `login()` for email-or-username**

```python
if "@" in payload.username:
    user = session.exec(
        select(WrapperUser).where(WrapperUser.email == payload.username)
    ).first()
else:
    user = session.exec(
        select(WrapperUser).where(WrapperUser.username == payload.username)
    ).first()
```

- [ ] **Step 4: Add 4 tests, run, commit**

---

## Task 5: python-flask-skel (seed + login-by-email)

**Files:**
- Create: `_skels/python-flask-skel/app/seed.py`
- Modify: `_skels/python-flask-skel/app/__init__.py` (or `create_app`)
- Modify: `_skels/python-flask-skel/app/routes.py`

- [ ] **Step 1: Create `app/seed.py`** — uses SQLAlchemy session, `hash_password()` from auth module

- [ ] **Step 2: Call seed from `create_app()` after DB init**

- [ ] **Step 3: Update `login()` for email-or-username**

```python
if "@" in username:
    user = db.session.query(User).filter_by(email=username).first()
else:
    user = db.session.query(User).filter_by(username=username).first()
```

- [ ] **Step 4: Add 4 tests, run, commit**

---

## Task 6: java-spring-skel (seed + login-by-email)

**Files:**
- Modify: `_skels/java-spring-skel/src/main/java/com/example/skel/config/SchemaInitializer.java`
- Modify: `_skels/java-spring-skel/src/main/java/com/example/skel/controller/AuthController.java`
- Modify: `_skels/java-spring-skel/src/test/java/com/example/skel/ApplicationTests.java`

- [ ] **Step 1: Add seed logic to `SchemaInitializer`**

Add `seedDefaultAccounts(jdbc, passwordEncoder)` method. Reads env vars with `System.getenv()` fallbacks. Checks `SELECT COUNT(*) FROM users WHERE username = ?`, inserts if missing. Call at end of existing `run()` method. Inject `PasswordEncoder` into the initializer.

- [ ] **Step 2: Update `login()` for email-or-username**

```java
String sql = body.username().contains("@")
    ? "SELECT id, username, password_hash FROM users WHERE email = ?"
    : "SELECT id, username, password_hash FROM users WHERE username = ?";
```

- [ ] **Step 3: Add 4 tests to `ApplicationTests.java`**

```java
@Test
void defaultUserCanLogin() throws Exception {
    mockMvc.perform(post("/api/auth/login")
            .contentType(MediaType.APPLICATION_JSON)
            .content("{ \"username\": \"user\", \"password\": \"secret\" }"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.access").isNotEmpty());
}

@Test
void defaultSuperuserCanLogin() throws Exception { /* same with admin/secret */ }

@Test
void loginByEmail() throws Exception { /* same with user@example.com/secret */ }

@Test
void loginByEmailSuperuser() throws Exception { /* same with admin@example.com/secret */ }
```

- [ ] **Step 4: Run tests, commit**

---

## Task 7: rust-actix-skel (seed + login-by-email)

**Files:**
- Create: `_skels/rust-actix-skel/src/seed.rs`
- Modify: `_skels/rust-actix-skel/src/main.rs`
- Modify: `_skels/rust-actix-skel/src/handlers/auth.rs`

- [ ] **Step 1: Create `src/seed.rs`**

Async function `seed_default_accounts(pool: &SqlitePool)`. Reads env vars with `env::var().unwrap_or_else()`. Uses `hash_password()` from `crate::auth`. Checks `SELECT id FROM users WHERE username = ?`, inserts if missing.

- [ ] **Step 2: Add `mod seed;` to main.rs, call after schema bootstrap**

- [ ] **Step 3: Update `login_handler` for email-or-username**

```rust
let sql = if p.username.contains('@') {
    "SELECT id, username, password_hash FROM users WHERE email = ?"
} else {
    "SELECT id, username, password_hash FROM users WHERE username = ?"
};
```

- [ ] **Step 4: Add tests, run, commit**

---

## Task 8: rust-axum-skel (seed + login-by-email)

Same pattern as Task 7. Identical `seed.rs`. Login handler uses Axum's `State(state)` pattern instead of `web::Data`.

**Files:**
- Create: `_skels/rust-axum-skel/src/seed.rs`
- Modify: `_skels/rust-axum-skel/src/main.rs`
- Modify: `_skels/rust-axum-skel/src/handlers/auth.rs`

- [ ] **Steps 1-4: Same as Task 7, adapted for Axum**
- [ ] **Step 5: Commit**

---

## Task 9: go-skel (seed + login-by-email)

**Files:**
- Create: `_skels/go-skel/internal/seed/seed.go`
- Modify: `_skels/go-skel/cmd/server/main.go`
- Modify: `_skels/go-skel/internal/handlers/handlers.go`

- [ ] **Step 1: Create `internal/seed/seed.go`**

`SeedDefaultAccounts(ctx, db)` function. Uses `auth.HashPassword()`. Reads env vars with helper `envOr(key, fallback)`.

- [ ] **Step 2: Call seed from `main.go` after schema init**

- [ ] **Step 3: Update `handleLogin` for email-or-username**

```go
var sql string
if strings.Contains(body.Username, "@") {
    sql = `SELECT id, username, password_hash FROM users WHERE email = ?`
} else {
    sql = `SELECT id, username, password_hash FROM users WHERE username = ?`
}
```

- [ ] **Step 4: Add tests, run, commit**

---

## Task 10: next-js-skel (seed + login-by-email)

**Files:**
- Create: `_skels/next-js-skel/src/lib/seed.js`
- Modify: `_skels/next-js-skel/src/app/api/auth/login/route.js`
- Modify: server init to call seed

- [ ] **Step 1: Create `src/lib/seed.js`**

`seedDefaultAccounts()` function. Uses `hashPassword()` from `./auth`. Reads `process.env.*` with fallbacks.

- [ ] **Step 2: Call seed from server init**

- [ ] **Step 3: Update login route for email-or-username**

```javascript
const column = username.includes('@') ? 'email' : 'username';
const user = db.prepare(`SELECT * FROM users WHERE ${column} = ?`).get(username);
```

- [ ] **Step 4: Add tests, run, commit**

---

## Task 11: Cross-stack test lib

**Files:**
- Modify: `_bin/_frontend_backend_lib.py`

- [ ] **Step 1: Add `check_seeded_accounts()` function**

Logs in with username and email for both default user and superuser. Verifies JWT works with GET /api/items. Prints checkmark for each success.

- [ ] **Step 2: Call `check_seeded_accounts()` in the canonical flow**

After server is up, before the register+login flow.

- [ ] **Step 3: Run a cross-stack test to verify**
- [ ] **Step 4: Commit**

---

## Task 12: Documentation updates

**Files:**
- Modify: `README.md`
- Modify: `_docs/DEPENDENCIES.md`
- Modify: `_docs/LLM-MAINTENANCE.md`

- [ ] **Step 1: Add "Default accounts" section to README.md and DEPENDENCIES.md**

Table with all 6 env vars, defaults, and notes. Mention that every backend seeds at startup and login accepts email or username.

- [ ] **Step 2: Update LLM-MAINTENANCE.md** with seeding behavior note
- [ ] **Step 3: Commit**

---

## Task 13: Full test run

- [ ] **Step 1: Run skeleton e2e tests** — `./test` — expected 8/8
- [ ] **Step 2: Run cross-stack tests** — `make test-cross-stack` — expected all passed with seeded account checks
- [ ] **Step 3: Run AI tests** — expected 54 passed
- [ ] **Step 4: Fix any failures, re-run until green**
