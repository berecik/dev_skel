# Default Credentials — Design Spec

## Summary

Add `USER_LOGIN`, `USER_PASSWORD`, `SUPERUSER_LOGIN`, `SUPERUSER_PASSWORD`
to the wrapper-shared `.env`. Every backend skeleton seeds these accounts
at startup (idempotent — skip if exists). Tests verify the seeded
accounts can log in.

## Environment variables

Added to `_skels/_common/common-wrapper.sh` `.env.example` template:

```env
USER_LOGIN=user
USER_PASSWORD=secret
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=secret
```

Defaults provide a working dev experience out of the box.

## Startup seeding

Runs after schema init in each backend. Pseudocode:

```
for (login, password, is_super) in [(USER_LOGIN, USER_PASSWORD, false),
                                     (SUPERUSER_LOGIN, SUPERUSER_PASSWORD, true)]:
    if user with username == login exists: log "already exists", skip
    else: insert user(username=login, email={login}@localhost,
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

- Idempotent: no error if user already exists
- Password hashed with same function as register endpoint
- INFO-level log message for each account

## Testing

Each backend adds two tests:

1. `test_default_user_can_login` — POST /api/auth/login with USER_LOGIN/USER_PASSWORD → 200
2. `test_default_superuser_can_login` — POST /api/auth/login with SUPERUSER_LOGIN/SUPERUSER_PASSWORD → 200

Both tests also verify the returned JWT works (GET /api/items → 200).

Cross-stack test lib (`_bin/_frontend_backend_lib.py`) gets a
`check_seeded_accounts()` function called by every `skel-test-react-*`
runner.
