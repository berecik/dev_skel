"""AI manifest for the ``ts-react-skel`` skeleton.

The React skeleton ships a complete working example: a typed
`src/api/items.ts` repository with JWT bearer auth, a `useItems` custom
hook (`src/hooks/use-items.ts`), `LoginForm` / `ItemForm` / `ItemList`
components, and an `App.tsx` that composes them. This manifest tells
``_bin/skel-gen-ai`` how to rewrite that `Item`-shaped layer for the
user's `{item_class}` entity while preserving the wrapper-shared env
plumbing in `vite.config.ts` + `src/config.ts`.

The frontend NEVER references `JWT_SECRET`. The Vite plugin in
`vite.config.ts` does not promote that env var into the bundle, so any
accidental reference would silently be `undefined`.
"""

SYSTEM_PROMPT = """\
You are a senior React 19 + TypeScript engineer regenerating one
source file inside the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The package root is `{service_subdir}/`. Source lives under `src/`.
- The package uses Vite + React 19 + strict TypeScript
  (`tsconfig.json` ships with `"jsx": "react-jsx"` and React 19's
  `JSX` namespace removal — explicit return types use
  `import {{ type ReactElement }} from 'react'`, NEVER `JSX.Element`).
- The wrapper-shared `config` lives in `src/config.ts` and is already
  populated by `vite.config.ts` from `<wrapper>/.env` and
  `<wrapper>/_shared/service-urls.env`. Read it via
  `import {{ config }} from './config';` (or `'../config'` from a
  subdirectory).
- The reference example exposes an `Item` repository: `src/api/items.ts`
  (typed fetch client + JWT bearer + AuthError class), a `useItems`
  custom hook in `src/hooks/use-items.ts`, and `LoginForm` / `ItemForm`
  / `ItemList` components in `src/components/`. The user is replacing
  the `Item` entity with `{item_class}` (snake_case `{item_name}`,
  plural `{items_plural}`).
- The backend route the new client calls is
  `${{config.backendUrl}}/api/{items_plural}/`.
- The wrapper-shared JWT auth layer is `src/auth/token-store.ts` +
  `src/auth/use-auth-token.ts`. The new files MUST reuse it via
  `import {{ getToken }} from '../auth/token-store';` (in the API
  client) and `import {{ useAuthToken }} from
  '../auth/use-auth-token';` (in components / hooks). NEVER duplicate
  the token storage logic.
- The wrapper-shared **React state management layer** lives in
  `src/state/` — `app-state-store.ts` (pub/sub store), `state-api.ts`
  (typed client for `${{config.backendUrl}}/api/state`),
  `use-app-state.ts` (`useAppState<T>(key, default)` hook), and
  `AppStateProvider.tsx` (Context provider that hydrates from the
  backend on login). Components persist UI slices (filters, sort
  order, preferences) by calling `useAppState`. Do NOT reinvent
  this — reuse the existing files exactly as the reference does.
  When a new component needs persistent state, import the hook:
  `import {{ useAppState }} from '../state/use-app-state';`.

Shared environment (CRITICAL — frontend-safe values only):
- `config.backendUrl` — base URL for backend calls. Compose endpoints
  as `${{config.backendUrl}}/api/{items_plural}` etc.
- `config.jwt.issuer` / `config.jwt.algorithm` / `config.jwt.accessTtl`
  / `config.jwt.refreshTtl` — public JWT claims for client-side audit.
- `config.jwt.secret` — **NEVER REFERENCE THIS**. The Vite plugin in
  `vite.config.ts` does not promote `JWT_SECRET` into the bundle. If
  you accidentally type `config.jwt.secret`, the build will succeed
  but the value will be `undefined`.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Strict TypeScript — every exported function has explicit parameter
  and return types. Use `import {{ type ReactElement }} from 'react'`
  for component return types.
- React 19 / React Router-free — function components with hooks
  (`useState`, `useEffect`, `useCallback`).
- 2-space indentation, single quotes, semicolons. Match the
  REFERENCE files exactly.
- Use the global `fetch` API for HTTP — no axios, no swr, no
  react-query.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `npm run build` after generation to confirm the new "
        "{item_class} layer compiles. The wrapper-shared "
        "`<wrapper>/.env` is already baked in via `vite.config.ts`."
    ),
    "targets": [
        {
            "path": "src/api/{items_plural}.ts",
            "template": "src/api/items.ts",
            "language": "typescript",
            "description": "src/api/{items_plural}.ts — typed fetch client",
            "prompt": """\
Rewrite `src/api/items.ts` as `src/api/{items_plural}.ts` for the
`{item_class}` entity.

Required transformations:
- Replace every `Item` / `items` token with `{item_class}` /
  `{items_plural}` (incl. type names, function names, and the
  `ITEMS_BASE` constant which becomes `{ITEMS_PLURAL}_BASE` —
  uppercase the slug).
- The new endpoint is
  `${{config.backendUrl}}/api/{items_plural}` instead of
  `/api/items`.
- The exported `{item_class}` interface keeps the same field shape
  as `Item` (`id`, `name`, `description`, `is_completed`,
  `created_at`, `updated_at`) — this matches the canonical
  shared-DB schema and lets the same backend serve the new client
  without migrations.
- Keep the `loginWithPassword`, `AuthError`, `RequestOptions`,
  `buildHeaders`, and `unwrap` helpers exactly as in the REFERENCE.
  They are framework-wide and do not change with the entity name.
- Keep the `complete{item_class}` helper (renamed from `completeItem`)
  pointing at `/{items_plural}/${{id}}/complete`.

REFERENCE (`src/api/items.ts`):
---
{template}
---
""",
        },
        {
            "path": "src/hooks/use-{items_plural}.ts",
            "template": "src/hooks/use-items.ts",
            "language": "typescript",
            "description": "src/hooks/use-{items_plural}.ts — custom hook",
            "prompt": """\
Rewrite `src/hooks/use-items.ts` as `src/hooks/use-{items_plural}.ts`.

Required transformations:
- Hook name: `use{item_class}s`.
- Result interface name: `Use{item_class}sResult`.
- Field names stay (`items`, `loading`, `error`, `refresh`, `create`,
  `complete`, `unauthorized`) but the array type becomes
  `{item_class}[]` and the `New{item_class}` import comes from
  `'../api/{items_plural}'`.
- All `Item` / `items` references become `{item_class}` / `{items_plural}`.
- Keep the `useState` / `useEffect` / `useCallback` / `useRef`
  pattern, the AuthError handling, the abort-controller cleanup, and
  the optimistic-merge logic in `create` exactly as the REFERENCE has
  them.
- Imports must continue to pull `useAuthToken` from
  `'../auth/use-auth-token'`. Do NOT duplicate the token store.

REFERENCE (`src/hooks/use-items.ts`):
---
{template}
---
""",
        },
        {
            "path": "src/components/{item_class}List.tsx",
            "template": "src/components/ItemList.tsx",
            "language": "typescript",
            "description": "src/components/{item_class}List.tsx — list component",
            "prompt": """\
Rewrite `src/components/ItemList.tsx` as
`src/components/{item_class}List.tsx`.

Required transformations:
- Component name: `{item_class}List`.
- Props interface: `{item_class}ListProps`.
- The `items: Item[]` prop becomes `{items_plural}: {item_class}[]` —
  rename the prop AND every reference inside the component body.
- The `complete: (id: number) => Promise<Item>` prop type now returns
  `{item_class}`.
- The header text becomes `Items ({{...length}})` →
  `{item_class}s ({{...length}})` (use the user-facing plural).
- The `<section className="item-list">` className stays unchanged so
  the existing CSS keeps working — do NOT rename it. Same for the
  `item` / `done` / `badge` / `empty` / `status` classes.
- Imports: `import {{ type {item_class} }} from
  '../api/{items_plural}';`.

REFERENCE (`src/components/ItemList.tsx`):
---
{template}
---
""",
        },
        {
            "path": "src/components/{item_class}Form.tsx",
            "template": "src/components/ItemForm.tsx",
            "language": "typescript",
            "description": "src/components/{item_class}Form.tsx — create form",
            "prompt": """\
Rewrite `src/components/ItemForm.tsx` as
`src/components/{item_class}Form.tsx`.

Required transformations:
- Component name: `{item_class}Form`.
- Props interface: `{item_class}FormProps`.
- All `Item` / `items` references become `{item_class}` /
  `{items_plural}`. The `create` prop type is
  `(payload: New{item_class}) => Promise<{item_class}>`.
- The form className stays `item-form` (so the CSS keeps working) —
  do NOT rename it.
- Imports: `import {{ AuthError, type {item_class}, type
  New{item_class} }} from '../api/{items_plural}';`.

REFERENCE (`src/components/ItemForm.tsx`):
---
{template}
---
""",
        },
        {
            "path": "src/App.tsx",
            "template": "src/App.tsx",
            "language": "typescript",
            "description": "src/App.tsx — wire the new {item_class} components",
            "prompt": """\
Rewrite `src/App.tsx` to mount the new `{item_class}List`,
`{item_class}Form`, and the new `use{item_class}s` hook in place of
the reference `Item` / `useItems` plumbing.

Required transformations:
- Keep every import of `'./App.css'`, `{{ config }}` from `'./config'`,
  `LoginForm`, `useAuthToken`, and `AppStateProvider` exactly as in
  the REFERENCE.
- Replace the imports of `ItemForm`, `ItemList`, and `useItems`
  with the entity-specific equivalents:
  ```tsx
  import {item_class}Form from './components/{item_class}Form';
  import {item_class}List from './components/{item_class}List';
  import {{ use{item_class}s }} from './hooks/use-{items_plural}';
  ```
- Inside the **inner** `AuthenticatedApp` component, swap the
  `useItems()` call for `use{item_class}s()` and rename the
  destructured `items` field to `{items_plural}`.
- The `<{item_class}List>` invocation must pass
  `{items_plural}={{{items_plural}}}` (the renamed prop) plus
  `loading`, `error`, `refresh`, and `complete` exactly as the
  REFERENCE wires them.
- KEEP the `<AppStateProvider>` wrapper around `<AuthenticatedApp>` —
  it hydrates the wrapper-shared React state on login and persists
  any UI slices the new components write via `useAppState`.
- Keep the wrapper-shared `<header className="app-header">` block,
  including the `Backend URL` and `Sibling services` lines, unchanged.
- The `Sign out` button and the LoginForm fallback path stay
  identical.
- Component return type stays `ReactElement` (NOT `JSX.Element`).

REFERENCE (`src/App.tsx`):
---
{template}
---
""",
        },
    ],
}
