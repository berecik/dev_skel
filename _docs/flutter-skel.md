# flutter-skel

**Location**: `_skels/flutter-skel/`

**Framework**: Flutter (Material 3) + Dart, with `http`,
`flutter_secure_storage`, and `flutter_dotenv`

The Dart parallel of `ts-react-skel`. Generates a Flutter app that
pairs with the wrapper-shared `/api/items`, `/api/auth/login`, and
`/api/state` contract every dev_skel backend can serve.

## Structure

```
flutter-skel/
├── Makefile
├── gen                   # Generator script (runs `flutter create` then merges overlay)
├── merge                 # Merge overlay script
├── test_skel             # Skeleton E2E test (gen → flutter pub get → analyze → test)
├── deps                  # Check dependencies (flutter SDK)
├── install-deps          # Install dependencies
├── pubspec.yaml          # Pub deps overlay
├── analysis_options.yaml # Strict analyzer / lint config
├── AGENTS.md / CLAUDE.md / JUNIE-RULES.md
├── lib/
│   ├── main.dart                 # App entry — wires AuthScope + AppStateScope + MaterialApp
│   ├── config.dart               # Wrapper-shared env loaded via flutter_dotenv
│   ├── auth/
│   │   ├── token_store.dart      # ValueNotifier-backed singleton + flutter_secure_storage
│   │   └── auth_scope.dart       # InheritedNotifier exposing token to descendants
│   ├── api/
│   │   └── items_client.dart     # Typed http client (Item, NewItem, AuthError, login...)
│   ├── controllers/
│   │   └── items_controller.dart # ChangeNotifier wrapping the items client
│   ├── state/
│   │   ├── app_state_store.dart  # Pub/sub store for arbitrary JSON-serialisable slices
│   │   ├── state_api.dart        # Typed client for /api/state (load all + upsert + delete)
│   │   └── app_state_scope.dart  # InheritedNotifier hydrating store on login, resetting on logout
│   └── screens/
│       ├── login_screen.dart     # Username/password form
│       ├── home_screen.dart      # Composes form + list + sign-out
│       ├── item_form.dart        # Controlled form for creating items
│       └── item_list.dart        # Renders items + complete + persistent showCompleted filter
└── test/
    └── widget_test.dart          # Smoke test for the LoginScreen
```

## How it Works

1. The `gen` script runs `flutter create --platforms=...` to scaffold
   the platform directories (`android/`, `ios/`, `web/`, `macos/`,
   `linux/`, `windows/`) plus a placeholder `lib/main.dart`.
2. `merge` overlays every generator-owned file under `lib/` and
   `test/`, plus `pubspec.yaml` and `analysis_options.yaml`. Platform
   directories are excluded from the merge so `flutter create`'s
   output stays intact.
3. The Dart package name in `pubspec.yaml` is rewritten to match the
   chosen project subdir (with `-` → `_` per Dart's package-name
   rules), and every `package:flutter_skel/...` import inside `lib/`
   and `test/` is rewritten to use the new name so the project
   compiles without manual edits.
4. `flutter pub get` resolves the deps unless `--no-install` was
   passed.
5. `common-wrapper.sh` scaffolds the wrapper-level files (`./run`,
   `./test`, `./build`, `<wrapper>/.env`, `<wrapper>/_shared/`,
   etc.).
6. The wrapper-level `<wrapper>/.env` is copied into the project as
   the `.env` asset (declared in `pubspec.yaml`'s `flutter.assets`)
   so `flutter_dotenv` can load it at runtime.

## Dependencies Installed

Runtime (from `pubspec.yaml`):

- `http` — stdlib HTTP client
- `flutter_secure_storage` — Keychain (iOS/macOS) /
  EncryptedSharedPreferences (Android) / encrypted localStorage
  (web) / libsecret (Linux) / Credential Locker (Windows)
- `flutter_dotenv` — loads the bundled `.env` asset at startup

Dev:

- `flutter_test` (from the SDK)
- `flutter_lints` (canonical ruleset, tightened in
  `analysis_options.yaml`)

## Generation

From repo root:

```bash
make gen-flutter NAME=<target-path> [SERVICE="<display name>"] \
                  [PLATFORMS=web,android,ios,macos,linux,windows]
```

The default `PLATFORMS` value is **all six** so a single generation
produces a complete Flutter project tree. Trim it for a faster build:

```bash
make gen-flutter NAME=_test_projects/web-only PLATFORMS=web
```

From skeleton dir:

```bash
./gen <main-dir> [service_subdir] [--name <pkg>] [--org <reverse-dns>] \
                  [--platforms web,android,ios,macos,linux,windows] [--no-install]
```

### Options

| Option | Description |
|--------|-------------|
| `--name` | Override the Dart package name (defaults to the project subdir, dashes → underscores) |
| `--org` | iOS / Android bundle id prefix (defaults to `com.devskel`) |
| `--platforms` | Comma-separated platform list (defaults to all six) |
| `--no-install` | Skip `flutter pub get` |

## Generated Project Layout

```text
myapp/
  README.md             # wrapper README (common-wrapper.sh)
  Makefile              # wrapper Makefile (common-wrapper.sh)
  .env                  # wrapper-shared env (DATABASE_URL, JWT_*, BACKEND_URL, ...)
  _shared/              # shared SQLite + service-urls.env
  run test ...          # multi-service dispatch scripts
  frontend/             # the Flutter app
    pubspec.yaml
    analysis_options.yaml
    .env                # copy of ../.env (read by flutter_dotenv at runtime)
    lib/
    test/
    android/ ios/ web/ macos/ linux/ windows/   # written by flutter create
```

## Generated Project Usage

```bash
cd myapp/frontend

flutter pub get
flutter analyze       # static check
flutter test          # widget tests
flutter run -d chrome # launch on Flutter Web
flutter run -d ios    # launch on iOS simulator
```

The wrapper-level scripts also forward into the project:

```bash
cd myapp
./run            # delegates to frontend/ — equivalent to flutter run
./test           # delegates to frontend/ — runs flutter test
./build          # delegates to frontend/ — runs flutter build apk/web/...
```

## Wrapper-shared Contract

The Flutter app implements the same API contract as the React skel,
so a single backend can serve both clients without any per-frontend
shims:

| Endpoint | Where the Flutter side lives |
|---|---|
| `POST /api/auth/login` | `lib/api/items_client.dart` → `loginWithPassword` |
| `GET /api/items` | `lib/api/items_client.dart` → `listItems` |
| `POST /api/items` | `lib/api/items_client.dart` → `createItem` |
| `POST /api/items/{id}/complete` | `lib/api/items_client.dart` → `completeItem` |
| `GET /api/state` | `lib/state/state_api.dart` → `loadAllState` |
| `PUT /api/state/{key}` | `lib/state/state_api.dart` → `saveState` |
| `DELETE /api/state/{key}` | `lib/state/state_api.dart` → `deleteState` |

The JWT bearer token is stored via `flutter_secure_storage` and
exposed to the widget tree through the `AuthScope` `InheritedNotifier`.
The wrapper-shared env (`BACKEND_URL`, `JWT_ALGORITHM`, `JWT_ISSUER`,
…) is read once at app startup via `flutter_dotenv` and exposed
through `AppConfig`. `JWT_SECRET` is **never** loaded into
`AppConfig`, even if the wrapper `.env` contains it — secrets do not
belong in a mobile or web app bundle.

## Testing the Skeleton

```bash
cd _skels/flutter-skel
make test
```

Or from repo root:

```bash
make test-flutter
```

Both run `_skels/flutter-skel/test_skel`, which:

1. Generates a fresh project under `_test_projects/test-flutter-app`
2. Runs `flutter pub get`
3. Runs `flutter analyze` (soft check — warnings don't fail the run)
4. Runs `flutter test` (hard check)

The script auto-skips when `flutter` is not on the PATH so CI hosts
without the SDK stay green.

## AI Generation

The matching AI manifest lives at
`_skels/_common/manifests/flutter-skel.py` and exposes five targets
that mirror the React manifest:

1. `lib/api/{items_plural}_client.dart` (typed HTTP client)
2. `lib/controllers/{items_plural}_controller.dart` (view-model)
3. `lib/screens/{item_name}_list.dart` (list widget)
4. `lib/screens/{item_name}_form.dart` (create form)
5. `lib/screens/home_screen.dart` (composition wiring)

The wrapper-shared `lib/auth/`, `lib/config.dart`, and `lib/state/`
files are intentionally **not** in the target list — those are
infrastructure that every Flutter service in a wrapper relies on.

Run end-to-end against a local Ollama with:

```bash
make test-gen-ai-flutter
```

## Configuration

| Env var | Description |
|---|---|
| `SKEL_PROJECT_NAME` | Default Dart package name |
| `SKEL_ORG_REVERSE_DNS` | iOS / Android bundle id prefix (defaults to `com.devskel`) |
| `SKEL_AUTHOR_NAME` | Author name for `LICENSE` |
| `SKEL_LICENSE` | License (defaults to MIT) |
