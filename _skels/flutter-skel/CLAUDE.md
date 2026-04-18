# Claude Code Rules — `flutter-skel`

Claude-specific complement to `_skels/flutter-skel/AGENTS.md` and
`_skels/flutter-skel/JUNIE-RULES.md`. Read those first.


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

1. `_skels/flutter-skel/CLAUDE.md` (this file)
2. `_skels/flutter-skel/AGENTS.md`
3. `_skels/flutter-skel/JUNIE-RULES.md`
4. `_docs/flutter-skel.md`
5. `/CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
   `_docs/LLM-MAINTENANCE.md`

---

## 2. Skeleton Snapshot

- **Flutter** (Material 3) frontend with the stdlib `http` package,
  `flutter_secure_storage` for the JWT bearer token, and
  `flutter_dotenv` for the wrapper-shared `<wrapper>/.env`. Pinned
  via `pubspec.yaml` constraints — bump them in lock-step with the
  Flutter stable channel.
- Generated services live under `<wrapper>/<service_slug>/` (or
  `<wrapper>/frontend/` when no service name is supplied), the same
  layout the `ts-react-skel` uses.
- **Default backend pairing**: any backend that ships the wrapper-
  shared `/api/items` + `/api/auth/login` + `/api/state` contract.
  The two backends in `_bin/skel_ai_lib.py`'s `BACKENDS_WITH_ITEMS_API`
  set (`python-django-bolt-skel`, `python-fastapi-skel`) work out of
  the box; other backends still pair correctly for the auth flow but
  the items round-trip will 404 until the same routes exist there.
- **Default platforms**: all six (web, android, ios, macos, linux,
  windows). Trim with `make gen-flutter NAME=foo PLATFORMS=web` for a
  Flutter Web–only build.
- **Shipped working example** — the skel includes a complete typed
  item repository + JWT auth flow + Flutter state management layer
  that any dev_skel backend can serve:
  - `lib/config.dart` — wrapper-shared env, loaded via
    `flutter_dotenv` from the bundled `.env` asset (the gen script
    copies `<wrapper>/.env` into the project after running
    `common-wrapper.sh`). Exposes `config.backendUrl`,
    `config.jwt.{algorithm,issuer,accessTtl,refreshTtl}`, and
    `config.services` (slug → URL). Frontend NEVER references
    `JWT_SECRET` — `flutter_dotenv` reads everything in the bundled
    `.env`, so we deliberately omit secret keys from `AppConfig`
    even if a developer accidentally checks one in.
  - `lib/auth/token_store.dart` + `lib/auth/auth_scope.dart` —
    `ValueNotifier<String?>`-backed singleton wrapping
    `flutter_secure_storage` (Keychain on iOS, EncryptedSharedPreferences
    on Android, encrypted localStorage on web, libsecret on Linux,
    Credential Locker on Windows) plus an `InheritedNotifier` so any
    widget can call `AuthScope.of(context)` to read the token and
    rebuild on login/logout.
  - `lib/api/items_client.dart` — typed HTTP client (`listItems`,
    `getItem`, `createItem`, `completeItem`, `loginWithPassword`)
    hitting `${config.backendUrl}/api/items` with an automatic
    Bearer header from the token store and a custom `AuthError` for
    401 responses.
  - `lib/api/categories_client.dart` — typed HTTP client
    (`listCategories`, `getCategory`, `createCategory`,
    `updateCategory`, `deleteCategory`) hitting
    `${config.backendUrl}/api/categories` with the same auth
    pattern as the items client. Reuses `AuthError` from
    `items_client.dart`.
  - `lib/controllers/items_controller.dart` — `ChangeNotifier`-based
    view-model wrapping the client. Mirror of React's `useItems`
    hook: re-fetches when the token flips, surfaces 401s via the
    `unauthorized` flag, optimistically merges new items into the
    local cache.
  - `lib/controllers/categories_controller.dart` —
    `ChangeNotifier`-based view-model for categories. Same pattern
    as `ItemsController`: auto-refreshes on auth changes, holds a
    typed list with loading/error/unauthorized flags, supports
    create/update/delete with optimistic local cache updates.
  - `lib/state/` — wrapper-shared **Flutter state management layer**:
    - `app_state_store.dart` — `ChangeNotifier` with per-slice
      listeners for arbitrary JSON-serializable values.
    - `state_api.dart` — typed client for
      `${config.backendUrl}/api/state` (load all + upsert + delete).
    - `app_state_scope.dart` — `InheritedNotifier` plus a
      `StatefulWidget` that hydrates the store from the backend on
      login and resets it on logout. Exposes the
      `readAppState<T>(context, key, defaultValue: ...)` helper that
      mirrors React's `useAppState<T>(key, default)` hook.
  - `lib/screens/login_screen.dart` — `StatefulWidget` calling
    `ItemsClient.loginWithPassword`, then `TokenStore.setToken` on
    success.
  - `lib/screens/{item_form,item_list}.dart` — create form + list
    view sharing the `ItemsController` from the parent so creating
    an item refreshes the list optimistically. The list demonstrates
    `readAppState<bool>(context, 'items.showCompleted', defaultValue: true)`
    — a persistent filter that survives reloads via `/api/state`.
  - `lib/screens/home_screen.dart` — composes everything when
    authenticated: header (proves the wrapper-shared env wired
    correctly), `ItemForm`, `ItemListView`, sign-out IconButton.
  - `lib/main.dart` — wires `AuthScope` + `AppStateScope` +
    `MaterialApp` together; uses `ListenableBuilder(listenable:
    tokenStore)` to swap between LoginScreen and HomeScreen on
    login/logout.
- The generator runs `flutter create --platforms=...` then overlays
  skeleton files. The merge script's `OVERWRITE_PATTERN` lists every
  generator-owned file under `lib/` plus `pubspec.yaml`,
  `analysis_options.yaml`, and `test/widget_test.dart`. The pattern
  is the **source of truth** — keep it in sync whenever you add or
  rename a file in any of those directories, otherwise re-runs
  against an existing wrapper will silently leave stale copies in
  place.
- **Dart package name rewrite**: `pubspec.yaml` ships with `name:
  flutter_skel` and `lib/`/`test/` import via
  `package:flutter_skel/...`. The `gen` script rewrites both to the
  chosen project name (defaulting to the project subdir, with dashes
  → underscores per Dart's package-name rules) so generated apps
  compile without further edits.

---

## 3. Claude Operational Notes

1. **Always `Read` before editing.** Never modify the generator-owned
   files listed above through the skeleton; if you need to change
   them, change the `gen` / `merge` scripts so the generator handles
   it.
2. **Plan dependency bumps** that touch the Flutter stable channel,
   the Dart SDK constraint, or any of the four pub deps; confirm
   scope with the user before editing pinned versions.
3. **Default validation** (use `Bash`):
   ```bash
   make clean-test
   make test-generators
   cd _skels/flutter-skel && make test
   ```
4. Never hand-edit `_test_projects/test-flutter-app` — regenerate
   with `make gen-flutter NAME=_test_projects/<name>`.

---

## 4. Verification Checklist

- [ ] `make test-generators` is green (includes a Flutter `test_skel`
      run when the SDK is installed; auto-skips otherwise).
- [ ] Flutter skeleton-specific tests pass
      (`make test-flutter`).
- [ ] `flutter analyze` is clean against the shipped
      `analysis_options.yaml`.
- [ ] `OVERWRITE_PATTERN` in `merge` lists every file shipped under
      `lib/api/`, `lib/auth/`, `lib/controllers/`, `lib/screens/`,
      and `lib/state/`, plus `lib/main.dart`, `lib/config.dart`,
      `pubspec.yaml`, `analysis_options.yaml`, and
      `test/widget_test.dart`.
- [ ] No generator-owned files were hand-edited or copied via merge.
- [ ] AGENTS / CLAUDE / JUNIE rules still agree.
- [ ] AI manifest at `_skels/_common/manifests/flutter-skel.py` still
      lists the correct targets (and the templates they reference
      still exist on disk).
