# Junie Rules for `flutter-skel`

Specialised rules for Junie (and other LLM assistants) when working on
the `flutter-skel` skeleton.

Always read these rules **after** the global `_docs/JUNIE-RULES.md` and
`_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Dart + Flutter frontend skeleton.
- Lives at `_skels/flutter-skel/`.
- Generates a Flutter app that pairs with the wrapper-shared
  `/api/items`, `/api/auth/login`, and `/api/state` contract.
- Defaults to the **all-platforms** generation
  (`web,android,ios,macos,linux,windows`); trim with
  `make gen-flutter NAME=foo PLATFORMS=web` when only one is needed.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`,
   `flutter run`, etc.).
2. Keep Flutter SDK + pub deps reasonably up to date.
3. Ensure generated projects pair cleanly with any
   wrapper-shared backend.

---

## 2. Files to Check First

When working on `flutter-skel`, always inspect these files first:

1. Skeleton documentation: `_docs/flutter-skel.md` (if present).
2. Skeleton Makefile: `_skels/flutter-skel/Makefile`.
3. Generator scripts:
   - `_skels/flutter-skel/gen`
   - `_skels/flutter-skel/merge`
   - `_skels/flutter-skel/test_skel`
4. Dependency installers:
   - `_skels/flutter-skel/deps`
   - `_skels/flutter-skel/install-deps`
5. Core source tree under `_skels/flutter-skel/lib/` plus
   `_skels/flutter-skel/test/widget_test.dart`.
6. AI manifest: `_skels/_common/manifests/flutter-skel.py`.

Do **not** edit `_test_projects/*` directly; they are generated
output.

---

## 3. Version Management Rules (Flutter / Dart)

Whenever you touch this skeleton, consider whether dependency versions
should be updated.

1. Use the **current calendar date** to reason about which Flutter
   stable channel and Dart SDK constraint are "current".
2. Prefer the latest **stable** Flutter release supported by the
   `pubspec.yaml` constraint.
3. For pub.dev dependencies (`http`, `flutter_secure_storage`,
   `flutter_dotenv`, `flutter_lints`):
   - Prefer stable, widely used releases.
   - Avoid experimental or pre-release versions unless explicitly
     requested.
4. Do **not** fabricate version numbers. If you cannot check current
   versions, keep existing pins and document in commit messages that
   versions were not updated due to unavailable information.

After material dependency updates, run at least:

```bash
make clean-test
make test-generators
```

---

## 4. Architecture and Style Constraints

1. Keep the project structure aligned with the Flutter layout
   established by the generator (`lib/{api,auth,controllers,screens,state}/`,
   `test/`).
2. Follow existing patterns in `lib/main.dart`, `lib/api/items_client.dart`,
   `lib/controllers/items_controller.dart`, and the screens.
3. Avoid adding framework-specific complexity (state managers like
   provider/riverpod/bloc, routing libraries like go_router/auto_route,
   serialization codegen like freezed/json_serializable) unless the
   user explicitly requests them and the manifest + tests are
   adjusted accordingly.

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run
at least:

```bash
make clean-test
make test-generators
```

Ensure that generated Flutter projects can:

1. Install dependencies via `flutter pub get`.
2. Pass `flutter analyze` against the strict `analysis_options.yaml`.
3. Run their tests via `flutter test`.

The skeleton-level harness is `make test-flutter`, which runs
`_skels/flutter-skel/test_skel`.

---

## 6. Do Not

1. Do **not** overwrite generator-owned files inside generated
   projects without going through the `gen` / `merge` scripts.
2. Do **not** add files under `lib/` without listing them in
   `merge`'s `OVERWRITE_PATTERN` — re-runs against an existing
   wrapper would silently leave stale copies in place.
3. Do **not** edit the platform scaffolds (`android/`, `ios/`,
   `web/`, `macos/`, `linux/`, `windows/`) through the skeleton —
   they are written by `flutter create` and the `merge` script
   excludes them by design.
4. Do **not** upgrade major Flutter or Dart SDK versions without
   running the generator tests and verifying that generated apps
   still build and test.
