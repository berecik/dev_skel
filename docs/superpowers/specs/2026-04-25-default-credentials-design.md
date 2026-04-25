# Default Credentials — Design Spec

## Summary

Add default account env vars to the wrapper-shared `.env`. Every backend
skeleton seeds these accounts at startup (idempotent). Every backend's
login endpoint accepts **email or username**. Tests verify the seeded
accounts can log in by both methods.

## Environment variables

Added to `_skels/_common/common-wrapper.sh` `.env.example` template:

```env
# ----- Default accounts (seeded on first startup) ------------------------- #
USER_LOGIN=user
USER_EMAIL=user@example.com
USER_PASSWORD=secret
SUPERUSER_LOGIN=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=secret
```

All six always present with defaults. Each backend reads them at startup.

## Login by email or username

Currently all 9 backends accept only `{"username": "..."}` for login.
The login endpoint in every backend is updated so the `username` field
accepts **either a username or an email address**. The lookup becomes:

```
if "@" in value:
    user = find_by_email(value)
else:
    user = find_by_username(value)
```

No new JSON field — the existing `username` field is overloaded. This
keeps the frontend contract (`src/api/auth.ts`, cross-stack tests,
Playwright E2E) unchanged.

### Per-skeleton login changes

| Skeleton | File | Change |
|----------|------|--------|
| python-django-bolt-skel | `app/services/auth_service.py` | `authenticate_user()`: if `@` in username → `User.objects.get(email=...)` |
| python-django-skel | `app/views.py` | `LoginView.post()`: if `@` → filter by email instead of `authenticate()` |
| python-fastapi-skel | `app/wrapper_api/auth.py` | `login()`: if `@` → `.where(WrapperUser.email == ...)` |
| python-flask-skel | `app/routes.py` | `login()`: if `@` → `.filter_by(email=...)` |
| java-spring-skel | `AuthController.java` | `login()`: if contains `@` → `WHERE email = ?` |
| rust-actix-skel | `src/handlers/auth.rs` | `login_handler()`: if contains `@` → `WHERE email = ?` |
| rust-axum-skel | `src/handlers/auth.rs` | `login_handler()`: if contains `@` → `WHERE email = ?` |
| go-skel | `internal/handlers/handlers.go` | `handleLogin()`: if contains `@` → `WHERE email = ?` |
| next-js-skel | `src/app/api/auth/login/route.js` | if contains `@` → `WHERE email = ?` |

## Startup seeding

Runs after schema init in each backend. Pseudocode:

```
for (login, email, password, is_super) in [
    (USER_LOGIN, USER_EMAIL, USER_PASSWORD, false),
    (SUPERUSER_LOGIN, SUPERUSER_EMAIL, SUPERUSER_PASSWORD, true),
]:
    if user with username == login exists: log "already exists", skip
    else: insert user(username=login, email=email,
                      password=hash(password), is_superuser=is_super)
          log "Created default user '{login}'"
```

### Per-skeleton hook points

| Skeleton | Hook location |
|----------|---------------|
| python-django-bolt-skel | Post-migrate signal or AppConfig.ready() |
| python-django-skel | Post-migrate signal or AppConfig.ready() |
| python-fastapi-skel | FastAPI lifespan startup |
| python-flask-skel | create_app() after DB init |
| java-spring-skel | SchemaInitializer (existing startup bean) |
| rust-actix-skel | main() after schema bootstrap |
| rust-axum-skel | main() after schema bootstrap |
| go-skel | main() after schema bootstrap |
| next-js-skel | server init / seed module |

### Rules

- Idempotent: no error if user already exists (check by username)
- Password hashed with same function as register endpoint
- INFO-level log message for each account

## Testing

Each backend adds tests:

1. `test_default_user_can_login` — login with USER_LOGIN/USER_PASSWORD → 200
2. `test_default_superuser_can_login` — login with SUPERUSER_LOGIN/SUPERUSER_PASSWORD → 200
3. `test_login_by_email` — login with USER_EMAIL/USER_PASSWORD → 200
4. `test_login_by_email_superuser` — login with SUPERUSER_EMAIL/SUPERUSER_PASSWORD → 200

All tests verify the returned JWT works (GET /api/items → 200).

Cross-stack test lib (`_bin/_frontend_backend_lib.py`) gets a
`check_seeded_accounts()` function that:
- Logs in with username → expects 200
- Logs in with email → expects 200
- Uses returned JWT for an authenticated request → expects 200

Every `skel-test-react-*` runner calls `check_seeded_accounts()`.

## Documentation updates

- `_skels/_common/common-wrapper.sh` — env template with new vars
- `README.md` — add default credentials to env var table
- `_docs/DEPENDENCIES.md` — same
- `_docs/LLM-MAINTENANCE.md` — mention seeding behavior
- Per-skeleton AGENTS.md / CLAUDE.md — note the login-by-email change
