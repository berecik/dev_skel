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
- CRITICAL: The `Category` class from `package:flutter/foundation.dart`
  CONFLICTS with our `ItemCategory` class from
  `lib/api/categories_client.dart`. ALWAYS use `ItemCategory` from
  `'../api/categories_client.dart'` (or the appropriate relative
  path), NEVER a bare `Category` type. The categories client, the
  categories controller, and all widgets that reference categories
  use `ItemCategory` — not `Category`.
- CRITICAL: `lib/main.dart` is NOT regenerated by the AI. It
  constructs `DevSkelApp` with FIXED parameter names
  (`itemsController`, `categoriesController`, etc.) and
  `HomeScreen` with FIXED parameter names (`itemsController`,
  `categoriesController`). Do NOT rename these constructor
  parameters in `home_screen.dart` or any widget that `main.dart`
  instantiates — only the TYPE may change (e.g. from
  `ItemsController` to `{item_class}sController`), the NAME must
  stay `itemsController`.

User-supplied frontend instructions (apply these instead of the generic
screens when they ask for a richer domain UX — add extra screens,
navigation flows, etc. as described):
{frontend_extra}
"""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": (
        "Run `flutter analyze` and `flutter test` after generation to "
        "confirm the new {item_class} layer compiles. "
        "The screen widgets (`ItemForm`, `ItemListView`) keep their "
        "original class names to stay compatible with `home_screen.dart` "
        "and `main.dart` — only the internal entity references change. "
        "The wrapper-shared `<wrapper>/.env` is baked in via "
        "`lib/config.dart` + `flutter_dotenv`, and `lib/auth/`, "
        "`lib/state/`, and `lib/config.dart` are left untouched."
    ),
    "targets": [
        {
            "path": "lib/api/{items_plural}_client.dart",
            # Dynamic template path: for non-colliding item_class
            # values (Ticket, Booking, etc.) the path resolves to a
            # file that doesn't exist and the AI falls back to the
            # inline reference baked into the prompt.
            "template": "lib/api/{items_plural}_client.dart",
            # When item_class collides with a class the bundled
            # flutter-skel already ships rich (Order/OrderDetail/
            # OrderLine/OrderAddress, Category/ItemCategory,
            # CatalogItem, ReactState), skip the AI rewrite entirely
            # — the bundled file already matches the wrapper-shared
            # backend contract and is consumed by sibling widgets
            # (lib/screens/order_list.dart) that the AI does NOT
            # regenerate.
            "skip_for_item_class": [
                "Order", "OrderDetail", "OrderLine", "OrderAddress",
                "Category", "ItemCategory", "CatalogItem", "ReactState",
            ],
            "language": "dart",
            "description": "lib/api/{items_plural}_client.dart — typed HTTP client",
            "prompt": """\
Produce `lib/api/{items_plural}_client.dart` for the `{item_class}`
entity. The REFERENCE template (block at the bottom of this prompt
under "REFERENCE") is one of two things, and your task differs based
on which:

  PATH A — {item_class} is one of these EXACT names:
  `Order`, `Category`, `CatalogItem`, `ReactState`, `OrderLine`,
  `OrderAddress`, `OrderDetail`. These names refer to classes the
  bundled flutter-skel already ships at full domain richness in the
  REFERENCE template at this path. In PATH A, OUTPUT THE REFERENCE
  VERBATIM (or with at most additive changes the frontend
  instructions explicitly demand). DO NOT replace its rich domain
  shape with the generic items shape under any circumstance. The
  bundled file already matches the wrapper-shared backend contract
  and is consumed by the bundled `lib/screens/order_list.dart`
  widget; rewriting it breaks that widget.

  PATH B — {item_class} is anything else (Ticket, Booking, Pizza).
  In PATH B, the REFERENCE template is either the bundled
  items_client.dart (when path resolves to it) or
  `(no template provided)` (when nothing exists at this path). Then
  RENAME items → {items_plural} throughout (class names, factory
  names, the `_itemsBase` getter → `_{items_plural}Base`, method
  names like `listItems` → `list{item_class}s`, `getItem` →
  `get{item_class}`, `createItem` → `create{item_class}`,
  `completeItem` → `complete{item_class}`) and apply the user's
  frontend instructions to enrich the class shape with any
  domain-specific fields, companion classes, and methods.

Common rules (apply in BOTH paths):
- The HTTP endpoint is `${{config.backendUrl}}/api/{items_plural}`.
- Imports continue to pull `TokenStore` from
  `'../auth/token_store.dart'` and `AppConfig` from
  `'../config.dart'`.

User-supplied frontend instructions (apply additively in PATH A,
substantively in PATH B):
----- BEGIN FRONTEND INSTRUCTIONS -----
{frontend_extra}
-----  END FRONTEND INSTRUCTIONS  -----

- FALLBACK SHAPE (use ONLY when the frontend instructions above are
  empty or do not specify Dart class shapes). Keep ALL fields from
  the original `Item` class, including `categoryId`:
  ```dart
  class {item_class} {{
    const {item_class}({{
      required this.id,
      required this.name,
      required this.description,
      required this.isCompleted,
      required this.createdAt,
      required this.updatedAt,
      this.categoryId,
    }});

    final int id;
    final String name;
    final String? description;
    final bool isCompleted;
    final String createdAt;
    final String updatedAt;
    final int? categoryId;

    factory {item_class}.fromJson(Map<String, dynamic> json) {{
      return {item_class}(
        id: json['id'] as int,
        name: (json['name'] ?? '') as String,
        description: json['description'] as String?,
        isCompleted: (json['is_completed'] ?? false) as bool,
        createdAt: (json['created_at'] ?? '') as String,
        updatedAt: (json['updated_at'] ?? '') as String,
        categoryId: json['category_id'] as int?,
      );
    }}
  }}

  class New{item_class} {{
    const New{item_class}({{
      required this.name,
      this.description,
      this.isCompleted,
      this.categoryId,
    }});

    final String name;
    final String? description;
    final bool? isCompleted;
    final int? categoryId;

    Map<String, dynamic> toJson() {{
      final out = <String, dynamic>{{'name': name}};
      if (description != null) out['description'] = description;
      if (isCompleted != null) out['is_completed'] = isCompleted;
      if (categoryId != null) out['category_id'] = categoryId;
      return out;
    }}
  }}
  ```
  In fallback mode, `categoryId` is used by the form and list widgets
  for the category selector and badge display.
- AVOID DUPLICATING the `AuthError`, `loginWithPassword`, `_headers`,
  and `_unwrap` helpers. If `lib/api/items_client.dart` will continue
  to exist alongside this new client (which it will whenever the
  wrapper still ships an items endpoint), DO NOT redefine
  `AuthError` here — instead `import '../api/items_client.dart'
  show AuthError;` and use the imported symbol. Same for any other
  framework-wide types (`_headers`, `_unwrap` are private so they
  can be redefined; `AuthError` is public and would collide). If a
  symbol must be available to handlers in this file, prefer importing
  it over redeclaring it. Only redeclare `AuthError` here when
  `items_client.dart` will NOT be in the final tree.
- Keep the `complete{item_class}` helper (renamed from `completeItem`)
  pointing at `/{items_plural}/$id/complete`.
- The class name becomes `{item_class}sClient` (renamed from
  `ItemsClient`).
- Imports must continue to pull `TokenStore` from
  `'../auth/token_store.dart'` and `AppConfig` from
  `'../config.dart'`. Do NOT duplicate the token storage logic.
- IMPORTANT: The `Category` class from `package:flutter/foundation.dart`
  CONFLICTS with our `ItemCategory` class. NEVER import or use a bare
  `Category` type — always use `ItemCategory` from
  `'../api/categories_client.dart'` when referencing categories.

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
            # Dynamic template — see comment on the api client target.
            "template": "lib/controllers/{items_plural}_controller.dart",
            # See skip_for_item_class on the api client target above.
            "skip_for_item_class": [
                "Order", "OrderDetail", "OrderLine", "OrderAddress",
                "Category", "ItemCategory", "CatalogItem", "ReactState",
            ],
            "language": "dart",
            "description": "lib/controllers/{items_plural}_controller.dart — view-model",
            "prompt": """\
Produce `lib/controllers/{items_plural}_controller.dart`. The
REFERENCE template (block below) is one of two things; act based on
which:

  PATH A — {item_class} is one of these EXACT names:
  `Order`, `Category`, `CatalogItem`, `ReactState`, `OrderLine`,
  `OrderAddress`, `OrderDetail`. The bundled flutter-skel already
  ships a rich `{item_class}sController` at the REFERENCE path that
  matches the wrapper-shared backend contract. In PATH A, OUTPUT
  THE REFERENCE VERBATIM with at most additive changes the
  frontend instructions explicitly demand. Do NOT replace its
  methods with the generic items CRUD (`create`, `complete`) — the
  bundled controller is the contract `lib/screens/order_list.dart`
  consumes.

  PATH B — {item_class} is anything else (Ticket, Booking, Pizza).
  REFERENCE is the items_controller.dart baseline (or the
  `(no template provided)` placeholder). Then RENAME items →
  {items_plural} throughout (class name `ItemsController` →
  `{item_class}sController`, `_items` field → `_{items_plural}`,
  client type → `{item_class}sClient`, all `Item` / `items` tokens
  → `{item_class}` / `{items_plural}`) and apply the user's frontend
  instructions to add domain-specific methods (e.g. `getDetail`,
  `createDraft`, `addLine`, `submit`, `approve`, `reject`).

User-supplied frontend instructions:
----- BEGIN FRONTEND INSTRUCTIONS -----
{frontend_extra}
-----  END FRONTEND INSTRUCTIONS  -----

Required transformations (rename-only baseline for PATH B — the
domain instructions above SUPERSEDE these where they conflict):
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
- IMPORTANT: The `Category` class from `package:flutter/foundation.dart`
  CONFLICTS with our `ItemCategory` class. NEVER import or use a bare
  `Category` type — always use `ItemCategory` from
  `'../api/categories_client.dart'` when referencing categories.

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
            "path": "lib/screens/item_list.dart",
            "template": "lib/screens/item_list.dart",
            "language": "dart",
            "description": "lib/screens/item_list.dart — list widget",
            # When item_class collides with a bundled rich type, leave
            # the bundled simple-CRUD ItemListView in place — the rich
            # workflow is rendered by lib/screens/order_list.dart which
            # the AI does NOT regenerate.
            "skip_for_item_class": [
                "Order", "OrderDetail", "OrderLine", "OrderAddress",
                "Category", "ItemCategory", "CatalogItem", "ReactState",
            ],
            "prompt": """\
Produce `lib/screens/item_list.dart`. There are TWO paths:

  PATH A — {item_class} is one of these EXACT names:
  `Order`, `Category`, `CatalogItem`, `ReactState`, `OrderLine`,
  `OrderAddress`, `OrderDetail`. The bundled flutter-skel already
  ships richer companion widgets for these types (e.g.
  `OrderListView` in `lib/screens/order_list.dart`), and
  `home_screen.dart` mounts BOTH `ItemListView` and `OrderListView`
  side-by-side with their own controllers. Rewriting `ItemListView`
  to use `{item_class}sController` breaks that pairing.
  In PATH A, OUTPUT THE REFERENCE VERBATIM (or with at most
  whitespace-only changes). Do NOT change the entity type or
  controller type here.

  PATH B — {item_class} is anything else (Ticket, Booking, Pizza).
  Then RENAME items → {item_class} per the rules below.

CRITICAL: Keep the widget class name as `ItemListView` and the file
as `lib/screens/item_list.dart`. Do NOT rename the class — it MUST
stay `ItemListView` because `home_screen.dart` and `main.dart` import
it by this exact name.

Required transformations (PATH B only):
- Keep class name: `ItemListView` (do NOT change).
- The `controller` field type stays `ItemsController` from
  `'../controllers/items_controller.dart'` — do NOT rename.
- Update the item model type: `Item` references use `{item_class}`
  from `'../api/{items_plural}_client.dart'`.
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
- IMPORTANT: The `Category` class from `package:flutter/foundation.dart`
  CONFLICTS with our `ItemCategory` class. If this widget references
  categories (e.g. to display a category badge), ALWAYS use
  `ItemCategory` from `'../api/categories_client.dart'`, NEVER bare
  `Category`.

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
            "path": "lib/screens/item_form.dart",
            "template": "lib/screens/item_form.dart",
            "language": "dart",
            "description": "lib/screens/item_form.dart — create form",
            # When item_class collides with a bundled rich type, leave
            # the bundled simple-CRUD ItemForm in place — the rich
            # workflow is handled by lib/screens/order_list.dart which
            # the AI does NOT regenerate.
            "skip_for_item_class": [
                "Order", "OrderDetail", "OrderLine", "OrderAddress",
                "Category", "ItemCategory", "CatalogItem", "ReactState",
            ],
            "prompt": """\
Produce `lib/screens/item_form.dart`. The REFERENCE template is the
bundled simple-CRUD form. There are TWO paths:

  PATH A — {item_class} is one of these EXACT names:
  `Order`, `Category`, `CatalogItem`, `ReactState`, `OrderLine`,
  `OrderAddress`, `OrderDetail`. These names collide with classes
  the bundled flutter-skel already ships at full domain richness;
  the bundled `home_screen.dart` mounts `ItemListView` (Item-based)
  alongside `OrderListView` (Order-based) and passes the matching
  controller to each. Rewriting `ItemForm` to use
  `{item_class}sController` breaks that contract.
  In PATH A, OUTPUT THE REFERENCE VERBATIM (or with at most
  whitespace-only changes). Do NOT swap `ItemsController` for
  `{item_class}sController`. Do NOT import `New{item_class}` (the
  rich orders_client.dart does not define `NewOrder` — there is no
  simple create call for a rich workflow). Do NOT change the entity
  type referenced inside the form. The `Item` baseline stays.

  PATH B — {item_class} is anything else (Ticket, Booking, Pizza,
  etc.). Then RENAME items → {item_class} per the rules below.

CRITICAL: Keep the widget class name as `ItemForm` and the file as
`lib/screens/item_form.dart`. Do NOT rename the class — it MUST stay
`ItemForm` because `home_screen.dart` and `main.dart` import it by
this exact name.

Required transformations (PATH B only):
- Keep class name: `ItemForm` (do NOT change).
- The `controller` field type stays `ItemsController` — do NOT rename.
- The `controller.create(NewItem(...))` call becomes
  `controller.create(New{item_class}(...))` — import
  `New{item_class}` from `'../api/{items_plural}_client.dart'`.
- The card heading becomes `New {item_class}` (user-facing
  singular).
- Keep the controlled `TextEditingController` pattern, the
  AuthError handling, and the `_submitting` /
  `setState` flow exactly as the REFERENCE has them.
- CRITICAL: The widget MUST accept an optional
  `CategoriesController? categoriesController` parameter, exactly
  as the reference `ItemForm` does. The constructor signature is:
  ```dart
  const {item_class}Form({{
    super.key,
    required this.controller,
    this.categoriesController,
  }});

  final {item_class}sController controller;
  final CategoriesController? categoriesController;
  ```
- When `categoriesController` is non-null, render a
  `_CategoryDropdown` widget (or equivalent) that uses
  `ListenableBuilder(listenable: categoriesController)` to rebuild
  whenever categories change, and includes a
  `DropdownButtonFormField<int?>` iterating over the categories.
- The `_selectedCategoryId` state variable must be passed as
  `categoryId` in `New{item_class}(...)`.
- Import `CategoriesController` from
  `'../controllers/categories_controller.dart'`.
- IMPORTANT: The `Category` class from `package:flutter/foundation.dart`
  CONFLICTS with our `ItemCategory` class. In the category dropdown,
  iterate over `categoriesController.categories` which returns
  `List<ItemCategory>`. Use `ItemCategory` from
  `'../api/categories_client.dart'`, NEVER bare `Category`.

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
        # NOTE: home_screen.dart is NOT regenerated by the AI.
        # When item_class=Order, the renamed widgets (OrderListView,
        # OrdersController) collide with the existing orders module.
        # main.dart passes `itemsController: ItemsController` which
        # would mismatch if the AI rewrites the type. The items list
        # and form keep their original class names (ItemListView,
        # ItemForm) so home_screen.dart stays compatible.
    ],
}


# --------------------------------------------------------------------------- #
#  Integration manifest (second Ollama session)
# --------------------------------------------------------------------------- #
#
# After the per-target MANIFEST above generates the new Flutter service,
# ``_bin/skel-gen-ai`` runs a SECOND Ollama pass against the block below.
# The integration phase has access to a snapshot of every sibling service
# in the wrapper via the ``{wrapper_snapshot}`` placeholder so the model
# can ground its rewrites in real code.
#
# Targets here are *additive* — they create new files (sibling info,
# integration tests) without overwriting anything from the first phase.
# Each target's prompt receives the same template variables as the
# main MANIFEST plus:
#
#   - ``{wrapper_snapshot}`` — Markdown rendering of every sibling
#     service (slug, kind, tech, key files).
#   - ``{sibling_count}`` — number of siblings discovered.
#   - ``{sibling_slugs}`` — comma-separated list of sibling slugs (or
#     ``"(none)"`` when the new service is the only one in the wrapper).
#
# This is a **frontend** skeleton — there is no backend server to test
# against at integration time. Integration testing means verifying that
# the typed clients can be constructed, the `AppConfig` loads with the
# expected env vars, and the API client classes export the expected
# interface.
#
# After the integration files are written, the test-and-fix loop runs
# the ``test_command`` via `flutter test`. On failure, it asks Ollama
# to repair each integration file in turn, capped at ``fix_timeout_m``
# minutes.


INTEGRATION_SYSTEM_PROMPT = """\
You are a senior Flutter / Dart engineer integrating a freshly generated
frontend service into an existing dev_skel multi-service wrapper.

The new service is `{service_label}` (slug `{service_slug}`, tech
`flutter-skel`). It already ships:
- A typed `lib/api/items_client.dart` HTTP client with JWT bearer auth.
- A typed `lib/api/categories_client.dart` client (wrapper-shared).
- The wrapper-shared `lib/config.dart` (`AppConfig`) loaded at startup
  via `flutter_dotenv` from the bundled `.env` asset.
- The wrapper-shared `lib/state/` layer (`app_state_store.dart`,
  `state_api.dart`, `app_state_scope.dart`).
- The wrapper-shared `lib/auth/` layer (`token_store.dart`,
  `auth_scope.dart`).

This is a **frontend app** — it does NOT run its own HTTP server.
Integration testing here means:
- Verifying that `AppConfig` loads with a non-empty `backendUrl`.
- Verifying that the typed API client classes (`ItemsClient`,
  `CategoriesClient`, `StateApi`) can be constructed without errors.
- When sibling services exist in the wrapper, verifying that their
  URLs are present in the `AppConfig.services` map.
- All assertions are unit-level — NO live HTTP calls.

Sibling services already in the wrapper (snapshot of their key files
follows so you can ground your code in real signatures, not guesses):

{wrapper_snapshot}

Coding rules:
- Strict Dart — every public function has explicit parameter and
  return types. Prefer `final` for locals.
- Flutter null safety — use `?` for nullable types and `late` only
  when truly needed.
- 2-space indentation, single quotes, trailing commas in widget
  trees and parameter lists. Match the existing files exactly.
- Use the `http` package for HTTP — no `dio`, no `retrofit`.
- Use `flutter_test` for all tests (`import 'package:flutter_test/
  flutter_test.dart';`).
- Output ONLY the file's contents. No markdown fences, no commentary.
- When `{sibling_count}` is 0 the integration tests should still
  exercise the config shape and API client constructors. Do not
  assume sibling services exist; gracefully degrade.

User-supplied integration instructions (free-form, take with the same
weight as the rules above):
{integration_extra}

User-supplied frontend instructions (already applied during the
per-target phase, repeated here so the integration code stays
consistent):
{frontend_extra}
"""


INTEGRATION_MANIFEST = {
    "system_prompt": INTEGRATION_SYSTEM_PROMPT,
    "notes": (
        "Integration phase: writes lib/integration/sibling_info.dart "
        "and test/integration_test.dart, then runs the test-and-fix "
        "loop via `flutter test`."
    ),
    "test_command": "flutter test test/integration_test.dart",
    "fix_timeout_m": 60,
    "targets": [
        {
            "path": "lib/integration/sibling_info.dart",
            "language": "dart",
            "description": "lib/integration/sibling_info.dart — typed map of sibling service URLs",
            "prompt": """\
Write `lib/integration/sibling_info.dart`. The module reads sibling
URLs from `AppConfig.services` and exports a typed map of sibling
service URLs.

Wrapper snapshot (sibling services discovered, {sibling_count} total):
---
{wrapper_snapshot}
---

Required structure:

- Import `AppConfig` from `'package:{service_slug}/config.dart'`.
- Define a `Map<String, String> getSiblingServices(AppConfig config)`
  function that reads `config.services` and returns a map of slug →
  URL for every sibling whose URL is defined and non-empty.
- When `{sibling_count}` is 0, the function must still be valid and
  return an empty `<String, String>{{}}`.
- Use strict Dart with explicit types on every public function.
- 2-space indentation, single quotes, trailing commas.

Output the full file contents only.
""",
        },
        {
            "path": "test/integration_test.dart",
            "language": "dart",
            "description": "test/integration_test.dart — Dart integration checks",
            "prompt": """\
Write `test/integration_test.dart`. Dart tests that verify the
frontend's typed clients can be constructed and the `AppConfig`
contains the expected wrapper-shared values.

Wrapper snapshot:
---
{wrapper_snapshot}
---

Required tests (use `group` / `test` / `expect` from
`package:flutter_test/flutter_test.dart`):

1. `AppConfig` group:
   - Load `AppConfig` via `await AppConfig.load()` (or construct
     with test values if `load()` requires the bundled `.env`).
   - Assert `config.backendUrl` is non-empty.

2. `ItemsClient` group:
   - Construct `{item_class}sClient(config: config)` (pass a test
     `AppConfig` instance).
   - Assert the client is not null (i.e. it constructed without
     throwing).

3. `CategoriesClient` group:
   - Construct `CategoriesClient(config: config)`.
   - Assert the client is not null.

4. `StateApi` group:
   - Construct `StateApi(config: config)`.
   - Assert the client is not null.

5. **When `{sibling_count}` > 0**: add a `sibling URLs` group that:
   - Imports `getSiblingServices` from
     `'package:{service_slug}/integration/sibling_info.dart'`.
   - Asserts the returned map has at least one entry.
   - For each known sibling slug, asserts the corresponding URL is
     a non-empty string starting with `'http'`.

6. **When `{sibling_count}` is 0**: do NOT add any sibling URL test.

Imports:
- `import 'package:flutter_test/flutter_test.dart';`
- `import 'package:{service_slug}/config.dart';`
- `import 'package:{service_slug}/api/{items_plural}_client.dart';`
- `import 'package:{service_slug}/api/categories_client.dart';`
- `import 'package:{service_slug}/state/state_api.dart';`
- Other imports as needed per group.

Use 2-space indentation, single quotes, trailing commas.
Output the full file contents only.
""",
        },
    ],
}
