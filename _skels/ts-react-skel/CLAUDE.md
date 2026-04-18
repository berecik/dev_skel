# Claude Code Rules — `ts-react-skel`

Claude-specific complement to `_skels/ts-react-skel/AGENTS.md` and
`_skels/ts-react-skel/JUNIE-RULES.md`. Read those first.


## Mandatory Test Artifact Location

- **Mandatory:** Any testing projects, services, data, or files must be created only under `_test_projects/` (the dedicated directory for generated testing skeletons and related test artifacts).

---

## Maintenance Scenario ("let do maintenance" / "let do test-fix loop")

Use this shared scenario whenever the user asks for maintenance (for example: `let do maintenance` or `let do test-fix loop`).

- **1) Finish the requested implementation scenario first.**
- **2) Run tests for changed scope first**, then run full relevant test suites.
- **3) Test code safety** (security/safety checks relevant to the stack and changed paths).
- **4) Simplify and clean up code** (remove dead code, reduce complexity, keep style consistent).
- **5) Run all relevant tests again** after cleanup.
- **6) Fix every issue found** (tests, lint, safety, build, runtime).
- **7) Repeat steps 2–6 until no issues remain.**
- **8) Only then update and synchronize documentation/rules** (`README`, `_docs/`, skeleton docs, agent instructions) to match final behaviour.

This is the default maintenance/test-fix loop and should be commonly understood across all agent entrypoints.

---

## 1. Read These Files First (in order)

1. `_skels/ts-react-skel/CLAUDE.md` (this file)
2. `_skels/ts-react-skel/AGENTS.md`
3. `_skels/ts-react-skel/JUNIE-RULES.md`
4. `_docs/ts-react-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- **React 19** + Vite + TypeScript SPA frontend with Vitest, ESLint,
  Prettier. The skel pins `react@^19` / `react-dom@^19` /
  `@types/react@^19` in the gen script so version drift on bumps does
  not break the example.
- Generated services live under `<wrapper>/<service_slug>/` (or
  `<wrapper>/frontend/` when no service name is supplied).
- **Default backend pairing**: this skel is paired with
  `python-django-bolt-skel` via the wrapper-shared `BACKEND_URL`
  (defaults to `http://localhost:8000`). The django-bolt skel ships
  the `/api/items` CRUD resource and `/api/state` save/load
  endpoints the React example consumes out of the box. Any other
  backend that exposes the same routes works too — just point
  `BACKEND_URL` at it (or at one of the auto-generated
  `SERVICE_URL_<SLUG>` values from `_shared/service-urls.env`).
- **Shipped working example** — the skel includes a complete typed
  item repository + JWT auth flow + React state management layer
  that any dev_skel backend can serve:
  - `src/config.ts` — wrapper-shared env exposed via the Vite plugin
    (`config.backendUrl`, `config.jwt.issuer`, etc.). The Vite
    plugin in `vite.config.ts` resolves `VITE_BACKEND_URL` from
    `BACKEND_URL` first, then the first `SERVICE_URL_<SLUG>` it
    finds, then `http://localhost:8000`. Frontend NEVER references
    `JWT_SECRET` (the plugin does not promote it into the bundle).
  - `src/auth/token-store.ts` + `src/auth/use-auth-token.ts` — tiny
    pub/sub JWT token store backed by `localStorage` plus a
    `useAuthToken()` custom hook that re-renders subscribers on
    login/logout.
  - `src/api/items.ts` — typed fetch client (`listItems`, `getItem`,
    `createItem`, `completeItem`, `loginWithPassword`) hitting
    `${config.backendUrl}/api/items` with an optional Bearer header
    from the token store and a custom `AuthError` for 401 responses.
  - `src/hooks/use-items.ts` — `useItems()` custom hook wrapping the
    repository with `useState` + `useEffect` + `useCallback` +
    `useRef`. Re-fetches when the JWT changes. Surfaces 401s via an
    `unauthorized` flag and clears the stale token automatically.
  - `src/state/` — wrapper-shared **React state management layer**:
    - `app-state-store.ts` — pub/sub store for arbitrary
      JSON-serializable slices.
    - `state-api.ts` — typed client for
      `${config.backendUrl}/api/state` (load all + upsert + delete).
    - `use-app-state.ts` — `useAppState<T>(key, default)` hook that
      reads/writes from the store and persists to the backend.
    - `AppStateProvider.tsx` — Context provider that hydrates the
      store from the backend on login and resets on logout. The
      `<AppStateProvider>` wrapper in `App.tsx` is what makes the
      `useAppState` hook usable in any descendant component.
  - `src/components/LoginForm.tsx` — POSTs to
    `${config.backendUrl}/api/auth/login`, captures the access
    token, stores it.
  - `src/components/ItemForm.tsx` + `src/components/ItemList.tsx` —
    create form and list view sharing the `useItems` hook from the
    parent so creating an item refreshes the list optimistically.
    `ItemList` also demonstrates `useAppState<boolean>('items.showCompleted', true)`
    — a persistent filter that survives reloads via `/api/state`.
  - `src/App.tsx` — composes everything: shows `LoginForm` when
    unauthenticated, otherwise wraps `<AuthenticatedApp>` (form +
    list + sign-out button) in `<AppStateProvider>`.
- Component return types use `import { type ReactElement } from
  'react'` because **React 19 dropped the global `JSX` namespace** —
  `JSX.Element` no longer compiles under the strict `tsconfig.json`
  shipped here.
- The generator runs `npm create vite@latest --template react-swc-ts`
  then overlays skeleton files. The vite 8 template regressed and
  now ships a vanilla-TS scaffold (no React, no `index.html` with
  `#root`, no JSX in `tsconfig.json`), so the gen script explicitly
  installs `react`/`react-dom`/`@vitejs/plugin-react-swc` and the
  merge script's `OVERWRITE_PATTERN` includes `tsconfig.json`,
  `index.html`, `src/main.tsx`, `src/App.tsx`, `src/App.css`,
  `src/App.test.tsx`, `src/setupTests.ts`, `src/config.ts`,
  `vite.config.ts`, plus every file under `src/api/`, `src/auth/`,
  `src/hooks/`, `src/state/`, and the canonical
  `src/components/{LoginForm,ItemForm,ItemList}.tsx`. The
  `OVERWRITE_PATTERN` is the source of truth — keep it in sync
  whenever you add or rename a file in any of those directories,
  otherwise re-runs against an existing wrapper will silently leave
  stale copies in place.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing.** Never modify the generator-owned files
   listed above through the skeleton; if you need to change them, change the
   `gen` / `merge` scripts so the generator handles it.
2. **Plan dependency bumps** that touch React, Vite, TypeScript, or
   testing libraries; confirm scope with the user before editing pinned
   versions.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/ts-react-skel && make test
   ```
4. Never hand-edit `_test_projects/test-react-app` — regenerate with
   `make gen-react NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (includes a `npm run build`).
- [ ] React skeleton-specific tests pass.
- [ ] The built bundle still contains the wrapper-shared values
      (`devskel`, `HS256`, `BACKEND_URL` resolved value, `/api/items`,
      `/api/state`, `Bearer`) — `strings dist/assets/*.js | grep -E
      'devskel|api/items|api/state'`.
- [ ] `OVERWRITE_PATTERN` in `merge` lists every file shipped under
      `src/api/`, `src/auth/`, `src/hooks/`, `src/state/`, and
      `src/components/`.
- [ ] No generator-owned files were hand-edited or copied via merge.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
