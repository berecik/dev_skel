"""AI manifest for the ``flutter-skel`` skeleton.

The Flutter skeleton ships a complete working example: a typed
``lib/api/items_client.dart`` repository with JWT bearer auth, an
``ItemsController`` view-model (``lib/controllers/items_controller.dart``),
``LoginScreen`` / ``ItemForm`` / ``ItemListView`` screens, and a
``HomeScreen`` that composes them. This manifest tells
``_bin/skel-gen-ai`` how to rewrite that ``Item``-shaped layer for
the user's ``{item_class}`` entity while preserving the wrapper-shared
env plumbing in ``lib/config.dart``, the auth layer in ``lib/auth/``,
and the state layer in ``lib/state/``.

The frontend NEVER references ``JWT_SECRET`` — ``flutter_dotenv``
loads the bundled ``.env`` asset and ``AppConfig`` deliberately
omits the secret key even when the wrapper ``.env`` contains it.

Both the legacy ``{template}`` placeholder (full reference file) and
the new RAG-driven ``{retrieved_context}`` placeholder are wired into
every target's prompt — installing the RAG agent dependencies
(``make install-rag-deps``) automatically enriches the prompts with
retrieved chunks, while a clean install of just Ollama still works
because the legacy placeholder is always populated.
"""

SYSTEM_PROMPT = """\
You are a senior Flutter / Dart engineer regenerating one source file
inside the dev_skel `{skeleton_name}` skeleton.

Project layout:
- The package root is `{service_subdir}/`. Source lives under `lib/`.
- The package uses Flutter (Material 3) + Dart null safety with the
  strict `analysis_options.yaml` shipped here. Every public function
  has explicit parameter and return types.
- The wrapper-shared `AppConfig` lives in `lib/config.dart` and is
  loaded once at app startup via `flutter_dotenv` from the bundled
  `.env` asset (which the gen script copies from `<wrapper>/.env`).
  Read it via the `AppConfig` instance held in `lib/main.dart` —
  NEVER reach into `dotenv.env` directly from a screen or controller.
- The reference example exposes an `Item` repository:
  `lib/api/items_client.dart` (typed `http` client + Bearer header
  + AuthError class), an `ItemsController` view-model in
  `lib/controllers/items_controller.dart`, and `LoginScreen` /
  `ItemForm` / `ItemListView` widgets in `lib/screens/`. The user is
  replacing the `Item` entity with `{item_class}` (snake_case
  `{item_name}`, plural `{items_plural}`).
- The backend route the new client calls is
  `${{config.backendUrl}}/api/{items_plural}/`.
- The wrapper-shared JWT auth layer is `lib/auth/token_store.dart`
  + `lib/auth/auth_scope.dart`. The new files MUST reuse it via
  `import 'package:{service_slug}/auth/token_store.dart';` (in the
  client) and `AuthScope.read(context)` / `AuthScope.of(context)`
  (in widgets). NEVER duplicate the secure-storage logic.
- The wrapper-shared **Flutter state management layer** lives in
  `lib/state/` — `app_state_store.dart` (per-slice ChangeNotifier
  store), `state_api.dart` (typed client for
  `${{config.backendUrl}}/api/state`), `app_state_scope.dart`
  (`InheritedNotifier` + `readAppState<T>(context, key,
  defaultValue: ...)` helper that mirrors React's `useAppState`).
  Components persist UI slices (filters, sort order, preferences)
  by calling `readAppState<T>(...).set(next)`. Do NOT reinvent this
  — reuse the existing files exactly as the reference does. When a
  new widget needs persistent state, import the helper:
  `import 'package:{service_slug}/state/app_state_scope.dart';`.

Shared environment (CRITICAL — frontend-safe values only):
- `config.backendUrl` — base URL for backend calls. Compose endpoints
  as `'${{config.backendUrl}}/api/{items_plural}'` etc.
- `config.jwt.issuer` / `config.jwt.algorithm` / `config.jwt.accessTtl`
  / `config.jwt.refreshTtl` — public JWT claims for client-side
  audit.
- There is **no** `config.jwt.secret` field. `flutter_dotenv` reads
  the bundled `.env`, but `AppConfig` deliberately drops the
  `JWT_SECRET` key — secrets do not belong in a mobile or web app
  bundle. Do not reintroduce it.

Authentication style requested by the user: `{auth_type}`. Notes:
{auth_details}

Coding rules:
- Strict Dart — every public function has explicit parameter and
  return types. Prefer `final` for locals.
- Flutter null safety — use `?` for nullable types and `late` only
  when truly needed (not in this skeleton).
- 2-space indentation, single quotes, trailing commas in widget
  trees and parameter lists. Match the REFERENCE files exactly.
- Use the `http` package for HTTP — no `dio`, no `retrofit`.
- Use the built-in state primitives (`ValueNotifier`, `ChangeNotifier`,
  `InheritedNotifier`) — no `provider`, `riverpod`, `bloc`, `getx`.
- Output ONLY the file's contents. No markdown fences, no commentary.
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `flutter analyze` and `flutter test` after generation to "
        "confirm the new {item_class} layer compiles. The wrapper-shared "
        "`<wrapper>/.env` is already baked in via `lib/config.dart` + "
        "`flutter_dotenv`, and the AI generator left `lib/auth/`, "
        "`lib/state/`, and `lib/config.dart` untouched."
    ),
    "targets": [
        {
            "path": "lib/api/{items_plural}_client.dart",
            "template": "lib/api/items_client.dart",
            "language": "dart",
            "description": "lib/api/{items_plural}_client.dart — typed HTTP client",
            "prompt": """\
Rewrite `lib/api/items_client.dart` as
`lib/api/{items_plural}_client.dart` for the `{item_class}` entity.

Required transformations:
- Replace every `Item` / `items` token with `{item_class}` /
  `{items_plural}` (incl. class names, factory names, the
  `_itemsBase` getter which becomes `_{items_plural}Base`, and
  every method name like `listItems` → `list{item_class}s`,
  `getItem` → `get{item_class}`, `createItem` → `create{item_class}`,
  `completeItem` → `complete{item_class}`).
- The new endpoint is `${{config.backendUrl}}/api/{items_plural}`
  instead of `/api/items`.
- The exported `{item_class}` class keeps the same field shape as
  `Item` (`id`, `name`, `description`, `isCompleted`, `createdAt`,
  `updatedAt`) — this matches the canonical shared-DB schema and
  lets the same backend serve the new client without migrations.
- Keep the `loginWithPassword`, `AuthError`, `_headers`, and
  `_unwrap` helpers exactly as in the REFERENCE. They are
  framework-wide and do not change with the entity name.
- Keep the `complete{item_class}` helper (renamed from `completeItem`)
  pointing at `/{items_plural}/$id/complete`.
- The class name becomes `{item_class}sClient` (renamed from
  `ItemsClient`).
- Imports must continue to pull `TokenStore` from
  `'../auth/token_store.dart'` and `AppConfig` from
  `'../config.dart'`. Do NOT duplicate the token storage logic.

REFERENCE (`lib/api/items_client.dart`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "lib/controllers/{items_plural}_controller.dart",
            "template": "lib/controllers/items_controller.dart",
            "language": "dart",
            "description": "lib/controllers/{items_plural}_controller.dart — view-model",
            "prompt": """\
Rewrite `lib/controllers/items_controller.dart` as
`lib/controllers/{items_plural}_controller.dart`.

Required transformations:
- Class name: `{item_class}sController` (renamed from
  `ItemsController`).
- The `client` field type is `{item_class}sClient` from
  `'../api/{items_plural}_client.dart'`.
- The `_items` / `items` field becomes `_{items_plural}` /
  `{items_plural}` and the type is `List<{item_class}>`.
- All `Item` / `items` references become `{item_class}` /
  `{items_plural}`.
- The `create({item_class}` parameter type is `New{item_class}`.
- Keep the `ChangeNotifier` pattern, the AuthError handling, the
  token-store listener wiring (`tokenStore.addListener(...)` in the
  constructor + `removeListener` in `dispose`), the optimistic-merge
  in `create`, and the per-method `notifyListeners()` calls exactly
  as the REFERENCE has them.
- Imports must continue to pull `TokenStore` from
  `'../auth/token_store.dart'`. Do NOT duplicate the token storage
  logic.

REFERENCE (`lib/controllers/items_controller.dart`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "lib/screens/{item_name}_list.dart",
            "template": "lib/screens/item_list.dart",
            "language": "dart",
            "description": "lib/screens/{item_name}_list.dart — list widget",
            "prompt": """\
Rewrite `lib/screens/item_list.dart` as
`lib/screens/{item_name}_list.dart`.

Required transformations:
- Widget class name: `{item_class}ListView` (renamed from
  `ItemListView`).
- The `controller` field type is `{item_class}sController` from
  `'../controllers/{items_plural}_controller.dart'`.
- All `Item` / `items` references in the body become
  `{item_class}` / `{items_plural}` (variable names like
  `visible`, `items` → `visible{item_class}s`, `{items_plural}`).
- The header text becomes `{item_class}s ({{count}})` /
  `{item_class}s ({{visible}} of {{total}})` — use the user-facing
  plural noun.
- The persistent filter slice key stays `{items_plural}.showCompleted`
  (the slice naming is intentionally lowercase plural so the React
  and Flutter clients pointing at the same backend share the same
  state).
- Keep the `ListenableBuilder(listenable: Listenable.merge([...]))`
  reactivity pattern, the `readAppState<bool>(context, ...,
  defaultValue: true)` filter wiring, and the `Switch` /
  `IconButton` actions exactly as the REFERENCE has them.
- Imports must continue to pull `readAppState`, `AppStateScope`
  from `'../state/app_state_scope.dart'`. Do NOT duplicate the
  state layer.

REFERENCE (`lib/screens/item_list.dart`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "lib/screens/{item_name}_form.dart",
            "template": "lib/screens/item_form.dart",
            "language": "dart",
            "description": "lib/screens/{item_name}_form.dart — create form",
            "prompt": """\
Rewrite `lib/screens/item_form.dart` as
`lib/screens/{item_name}_form.dart`.

Required transformations:
- Widget class name: `{item_class}Form` (renamed from `ItemForm`).
- The `controller` field type is `{item_class}sController` from
  `'../controllers/{items_plural}_controller.dart'`.
- The `controller.create(NewItem(...))` call becomes
  `controller.create(New{item_class}(...))` — import
  `New{item_class}` from `'../api/{items_plural}_client.dart'`.
- The card heading becomes `New {item_class}` (user-facing
  singular).
- Keep the controlled `TextEditingController` pattern, the
  AuthError handling, and the `_submitting` /
  `setState` flow exactly as the REFERENCE has them.

REFERENCE (`lib/screens/item_form.dart`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
        {
            "path": "lib/screens/home_screen.dart",
            "template": "lib/screens/home_screen.dart",
            "language": "dart",
            "description": "lib/screens/home_screen.dart — wire the new {item_class} screens",
            "prompt": """\
Rewrite `lib/screens/home_screen.dart` to mount the new
`{item_class}sController`, `{item_class}Form`, and `{item_class}ListView`
in place of the reference `ItemsController` / `ItemForm` /
`ItemListView` plumbing.

Required transformations:
- The `itemsController` field type becomes `{item_class}sController`
  from `'../controllers/{items_plural}_controller.dart'` — rename
  the field as `{item_name}sController` so the Dart-style
  snake_case identifier matches the file name.
- Replace the imports of `ItemForm`, `ItemListView`, and
  `ItemsController` with the entity-specific equivalents:
  ```dart
  import '../controllers/{items_plural}_controller.dart';
  import '{item_name}_form.dart';
  import '{item_name}_list.dart';
  ```
- Inside the `Scaffold` body, swap the `ItemForm` and
  `ItemListView` invocations for `{item_class}Form` and
  `{item_class}ListView`, both passing the renamed
  `{item_name}sController` as their `controller` parameter.
- KEEP the wrapper-shared `_Header` block, the `AppBar` with the
  sign-out `IconButton`, and the `SafeArea` /
  `SingleChildScrollView` layout unchanged.
- KEEP the `AuthScope.read(context).clear` sign-out wiring.
- Imports must continue to pull `AuthScope` from
  `'../auth/auth_scope.dart'` and `AppConfig` from
  `'../config.dart'`.

REFERENCE (`lib/screens/home_screen.dart`):
---
{template}
---

ADDITIONAL CONTEXT (retrieved from the skeleton corpus by the local
RAG agent — use these for grounding when the REFERENCE alone is
ambiguous, do NOT copy verbatim):
{retrieved_context}
""",
        },
    ],
}
