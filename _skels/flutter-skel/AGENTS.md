# Agents Rules for `flutter-skel`

Specialised rules for AI agents (LLM assistants) when working on the
`flutter-skel` skeleton.

Always read these rules **after** the global `/AGENTS.md`,
`_docs/JUNIE-RULES.md`, and `_docs/LLM-MAINTENANCE.md` files.

---

## 1. Purpose of This Skeleton

- Provides a Dart + Flutter frontend skeleton.
- Lives at `_skels/flutter-skel/`.
- Generates a Flutter app (Material 3) used as a frontend pair for the
  wrapper-shared `/api/items`, `/api/auth/login`, and `/api/state`
  contract that `python-django-bolt-skel` and `python-fastapi-skel`
  ship out of the box.
- Default platforms: **all six** (`web,android,ios,macos,linux,windows`)
  so a single generation produces a full Flutter project tree. Trim
  with `make gen-flutter NAME=foo PLATFORMS=web` when only one is
  needed.

Your goal when editing this skeleton is to:

1. Keep the developer experience smooth (`./gen`, `./test`,
   `flutter run`, etc.).
2. Keep the Flutter SDK constraint and the third-party deps (`http`,
   `flutter_secure_storage`, `flutter_dotenv`, `flutter_lints`)
   reasonably current.
3. Ensure generated projects are easy to bootstrap and pair with any
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
5. Core source tree under `_skels/flutter-skel/lib/` and the test
   under `_skels/flutter-skel/test/`.
6. AI manifest: `_skels/_common/manifests/flutter-skel.py`.

Do **not** edit `_test_projects/*` directly; they are generated
output.

---

## 3. Version Management Rules (Flutter / Dart)

Whenever you touch this skeleton, consider whether dependency versions
should be updated.

1. Use the **current calendar date** to reason about which Flutter
   stable channel and Dart SDK constraint are "current".
2. Prefer the latest **stable** Flutter release. The skeleton's
   `pubspec.yaml` constraint is `flutter: '>=3.22.0'` and `sdk:
   '>=3.4.0 <4.0.0'`.
3. For pub.dev dependencies (`http`, `flutter_secure_storage`,
   `flutter_dotenv`, `flutter_lints`):
   - Prefer stable, widely used releases compatible with the chosen
     Flutter version.
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

1. **Generator-owned files** (also listed in `merge`'s
   `OVERWRITE_PATTERN`):
   - `pubspec.yaml`, `analysis_options.yaml`
   - `lib/main.dart`, `lib/config.dart`
   - `lib/auth/{token_store.dart, auth_scope.dart}`
   - `lib/api/items_client.dart`
   - `lib/state/{app_state_store.dart, state_api.dart, app_state_scope.dart}`
   - `lib/controllers/items_controller.dart`
   - `lib/screens/{login_screen.dart, home_screen.dart, item_form.dart, item_list.dart}`
   - `test/widget_test.dart`
   Whenever you add or rename one of these files, **also update**
   `merge`'s `OVERWRITE_PATTERN` so re-runs against an existing
   wrapper actually pick up the change.
2. The skeleton uses Flutter's **built-in** state primitives —
   `ValueNotifier`, `ChangeNotifier`, `InheritedNotifier`. Do NOT
   introduce `provider`, `riverpod`, `bloc`, `getx`, or any other
   third-party state library unless the user explicitly asks for it.
3. The HTTP layer uses the stdlib `http` package. Do NOT introduce
   `dio`, `chopper`, `retrofit`, `freezed`, `json_serializable`, etc.
   without an explicit request — the React skel intentionally avoids
   the equivalent React libraries and we mirror that minimalism.
4. **Authentication**: every authenticated request goes through
   `ItemsClient` (or a parallel client built the same way) which
   reads the token from `TokenStore.instance`. Never re-implement
   secure storage in a new file — extend `TokenStore` instead.
5. **Wrapper-shared env**: read everything via the `AppConfig` loaded
   in `lib/main.dart` (which calls `flutter_dotenv` against the
   bundled `.env` asset). Never read `dotenv.env` directly from a
   screen / controller.
6. **No `print()`** — use `debugPrint` or a logger if you must (the
   `analysis_options.yaml` enforces `avoid_print`).

---

## 5. Testing Expectations

Whenever you modify this skeleton in a non-trivial way, you must run
at least:

```bash
make clean-test
make test-generators
```

Ensure that generated Flutter projects can:

1. Resolve dependencies via `flutter pub get`.
2. Pass `flutter analyze` (the skeleton's `analysis_options.yaml` is
   strict — fix any warnings the changes introduce).
3. Pass `flutter test` (the shipped `test/widget_test.dart` is a
   smoke test that pumps the LoginScreen).

The skeleton-level harness is `make test-flutter`, which runs
`_skels/flutter-skel/test_skel` (generates a fresh project,
`flutter pub get`, `flutter analyze`, `flutter test`).

The AI generator pipeline is `make test-gen-ai-flutter`, which
exercises the `_skels/_common/manifests/flutter-skel.py` manifest
end-to-end via Ollama.

---

## 6. Do Not

1. Do **not** edit the platform directories (`android/`, `ios/`,
   `web/`, `macos/`, `linux/`, `windows/`) inside generated projects
   through the skeleton — they are written by `flutter create` and
   the `merge` script excludes them on purpose. Change `gen` if you
   need different `flutter create` flags.
2. Do **not** hand-edit `_test_projects/test-flutter-app/...` — the
   `test_skel` script regenerates it from scratch on every run.
3. Do **not** introduce a new state-management or HTTP-client
   dependency without updating this file, the `pubspec.yaml`, the
   `analysis_options.yaml`, the AI manifest, AND running the AI
   generator end-to-end against a real Ollama.
4. Do **not** remove the `lib/auth/`, `lib/state/`, or `lib/config.dart`
   layers from the AI manifest's "untouched" list — those files are
   wrapper-shared infrastructure that every Flutter service in a
   wrapper relies on, the same way `src/auth/`, `src/state/`, and
   `src/config.ts` work in the React skel.
