# next-js-skel — Next.js 15 API Backend

**Location**: `_skels/next-js-skel/`

**Framework**: Next.js 15 (App Router) with better-sqlite3 + jose JWT

**Items API contract**: **server** — ships the full wrapper-shared
`/api/auth/register`, `/api/auth/login`, `/api/items` CRUD,
`/api/items/{id}/complete`, and `/api/state` endpoints out of the box.
Pairs with `ts-react-skel` and `flutter-skel` frontends without extra
wiring.

---

## Stack

| Layer | Technology |
| ----- | ---------- |
| Framework | Next.js 15 App Router (API route handlers) |
| Database | better-sqlite3 (synchronous, wrapper-shared `DATABASE_URL`) |
| Auth | jose (JWT sign/verify) + bcryptjs (password hashing) |
| Env | dotenv (loads `<service>/.env` then `<wrapper>/.env`) |
| Lint | ESLint 9 + eslint-config-next |
| Format | Prettier 3 |
| Test | `node:test` + `node:assert` (stdlib) |

---

## Generated Project Layout

```
myapp/
├── .env                    # wrapper-shared (DATABASE_URL, JWT_SECRET, ...)
├── _shared/db.sqlite3      # wrapper-shared SQLite
├── items_api/              # Next.js service (slug from display name)
│   ├── package.json
│   ├── next.config.js      # standalone output for Docker
│   ├── src/
│   │   ├── config.js       # wrapper-shared env contract
│   │   ├── lib/
│   │   │   ├── db.js       # SQLite singleton (users + items + react_state tables)
│   │   │   ├── auth.js     # JWT + password utilities
│   │   │   ├── db.test.js
│   │   │   └── auth.test.js
│   │   └── app/
│   │       ├── layout.js / page.js
│   │       └── api/
│   │           ├── health/route.js
│   │           ├── auth/register/route.js
│   │           ├── auth/login/route.js
│   │           ├── items/route.js         # GET (list) + POST (create)
│   │           ├── items/[id]/route.js    # GET (retrieve)
│   │           ├── items/[id]/complete/route.js  # POST (complete)
│   │           ├── state/route.js         # GET (load all slices)
│   │           └── state/[key]/route.js   # PUT (upsert) + DELETE (drop)
│   ├── Dockerfile          # multi-stage (standalone output)
│   ├── .devcontainer/      # VS Code Dev Containers
│   ├── ai / backport       # in-service AI agent + backport
│   └── test / run / build / install-deps
└── (wrapper dispatch scripts)
```

---

## API Endpoints

All item and state endpoints require `Authorization: Bearer <jwt>`.

| Method | Path | Status | Body |
| ------ | ---- | ------ | ---- |
| POST | `/api/auth/register` | 201 | `{user: {id, username, email}}` |
| POST | `/api/auth/login` | 200 | `{access: "<jwt>"}` |
| GET | `/api/items` | 200 | `[{id, name, description, is_completed, ...}]` |
| POST | `/api/items` | 201 | `{id, name, description, is_completed}` |
| GET | `/api/items/:id` | 200 | `{id, name, description, is_completed}` |
| POST | `/api/items/:id/complete` | 200 | `{id, ..., is_completed: true}` |
| GET | `/api/state` | 200 | `{key: jsonString, ...}` |
| PUT | `/api/state/:key` | 200 | body: `{value: "<json>"}` |
| DELETE | `/api/state/:key` | 200 | `{deleted: key}` |
| GET | `/api/health` | 200 | `{status: "ok"}` |

---

## Quick start

```bash
# Generate via the full-stack dialog (next-js-skel as backend)
_bin/skel-gen-ai myproj --backend next-js-skel --frontend ts-react-skel

# Or static (no Ollama)
_bin/skel-gen-static myproj next-js-skel "Items API"
make gen-nextjs NAME=myproj SERVICE="Items API"

cd myproj
./install-deps
./run dev         # Next.js dev server (PORT defaults to 3000)
./test            # node:test unit tests
```

The Next.js server reads `PORT` from the environment (default 3000).
Override with `PORT=8000 ./run dev`.

---

## Cross-stack integration test

```bash
make test-react-nextjs          # full 9-step HTTP + vitest smoke + Playwright E2E
make test-react-nextjs-keep     # leave the wrapper on disk for debugging
```

The test generates a wrapper with `next-js-skel` + `ts-react-skel`, builds
the React bundle, starts the Next.js dev server, and exercises the
complete `register → login → CRUD → complete → anonymous → invalid`
flow over real HTTP — plus the React vitest smoke (which calls
`/api/state` via the `state-api.ts` client) and a Playwright E2E
browser test.

---

## Docker

```bash
./build                     # multi-stage: npm ci → next build → standalone
./build --tag myapp:v1
./run docker                # docker run on port 3000
```

The Dockerfile uses Next.js standalone output mode (`output:
'standalone'` in `next.config.js`) for minimal production images.

---

## Config contract

`src/config.js` loads `<service>/.env` first, then `<wrapper>/.env`
(dotenv won't overwrite). This is the same contract every dev_skel
backend uses — a token issued by the Next.js service is accepted by
every other service in the same wrapper.

```javascript
import { config } from './config';
// config.databaseUrl  — "sqlite:///path" or "postgresql://..."
// config.dbPath       — raw file path for SQLite
// config.jwt.secret   — from JWT_SECRET env
// config.jwt.issuer   — "devskel"
// config.service.port — from PORT or SERVICE_PORT env
```
