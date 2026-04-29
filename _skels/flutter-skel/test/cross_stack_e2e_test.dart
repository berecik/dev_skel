/// Cross-stack END-TO-END test — drives the REAL widget tree against
/// a live backend.
///
/// Where the sibling `cross_stack_smoke_test.dart` exercises the
/// `lib/api/items_client.dart` + `lib/state/state_api.dart` *clients*
/// directly (raw API calls, no widgets), this file exercises the
/// **complete production widget tree** the user actually sees:
///
///   1. Pump `DevSkelApp` with real `ItemsClient` / `StateApi` /
///      `ItemsController` / `AppStateStore` instances pointing at
///      the live backend (URL injected via `BACKEND_URL`).
///   2. Find the `LoginScreen` by its "Sign in" heading.
///   3. Type credentials into the username + password `TextField`s
///      and tap the "Sign in" `FilledButton`.
///   4. Wait for `HomeScreen` to appear ("Items …" heading from
///      `ItemListView`).
///   5. Type a unique-per-run name into the `ItemForm` and tap
///      "Create item".
///   6. Verify the new item shows up in the `ItemListView`.
///   7. Tap "Mark complete" on the row matching that item.
///   8. Verify the row swaps to the "✓ done" `Chip`.
///   9. Verify the persistent-filter `Switch` exists and toggles cleanly.
///
/// Mirrors React's `e2e/items-e2e.spec.ts` at the level of "the
/// widget tree wires up correctly against the live backend". The
/// React E2E exercises a real Chromium browser; we exercise the
/// real widget tree via `WidgetTester` against the real backend.
/// Both prove the same contract from different angles.
///
/// Same gating contract as the smoke test:
///
///   RUN_CROSS_STACK_E2E=1   — gate (every other `flutter test` skips)
///   BACKEND_URL=http://...  — base URL the runner exposed
///
/// Implementation notes:
///   - Uses [LiveTestWidgetsFlutterBinding] so HTTP overrides do
///     not block real backend calls.
///   - Item names include a unique suffix so successive runs against
///     the same shared `items` table don't collide.
///   - We construct an [AppConfig] manually (skipping
///     `AppConfig.load()` which goes through `flutter_dotenv` and
///     panics under `flutter test`).
///   - `TokenStore.instance.value = ...` bypasses
///     `flutter_secure_storage`'s platform channels.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_skel/api/items_client.dart';
import 'package:flutter_skel/api/categories_client.dart';
import 'package:flutter_skel/api/orders_client.dart';
import 'package:flutter_skel/auth/token_store.dart';
import 'package:flutter_skel/config.dart';
import 'package:flutter_skel/controllers/items_controller.dart';
import 'package:flutter_skel/controllers/categories_controller.dart';
import 'package:flutter_skel/controllers/orders_controller.dart';
import 'package:flutter_skel/main.dart';
import 'package:flutter_skel/state/app_state_store.dart';
import 'package:flutter_skel/state/state_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

const _e2eUsername = 'flutter-e2e-user';
const _e2ePassword = 'flutter-e2e-pw-12345';
const _e2eEmail = 'flutter-e2e@example.com';

/// Register the canonical E2E user via raw HTTP. Accepts 201
/// (new), 400 (FastAPI: username exists), and 409 (Django: conflict)
/// so re-runs against any backend stay idempotent.
Future<void> _registerUser(String backendUrl) async {
  final response = await http.post(
    Uri.parse('$backendUrl/api/auth/register'),
    headers: const <String, String>{'Content-Type': 'application/json'},
    body: jsonEncode(const <String, String>{
      'username': _e2eUsername,
      'email': _e2eEmail,
      'password': _e2ePassword,
      'password_confirm': _e2ePassword,
    }),
  );
  if (response.statusCode != 201 &&
      response.statusCode != 400 &&
      response.statusCode != 409) {
    fail(
      'register expected 201/400/409, got ${response.statusCode}: ${response.body}',
    );
  }
}

/// Build a fresh widget tree pointed at the live backend.
({
  AppConfig config,
  TokenStore tokenStore,
  ItemsClient itemsClient,
  ItemsController itemsController,
  CategoriesController categoriesController,
  OrdersController ordersController,
  AppStateStore appStateStore,
  StateApi stateApi,
}) _buildTree(String backendUrl) {
  final config = AppConfig(
    backendUrl: backendUrl,
    jwt: const JwtConfig(
      algorithm: 'HS256',
      issuer: 'devskel',
      accessTtl: 3600,
      refreshTtl: 604800,
    ),
    services: const <String, String>{},
  );
  final tokenStore = TokenStore.instance;
  final itemsClient = ItemsClient(config: config, tokenStore: tokenStore);
  final stateApi = StateApi(config: config, tokenStore: tokenStore);
  final appStateStore = AppStateStore();
  final itemsController = ItemsController(
    client: itemsClient,
    tokenStore: tokenStore,
  );
  final categoriesClient = CategoriesClient(config: config, tokenStore: tokenStore);
  final categoriesController = CategoriesController(
    client: categoriesClient,
    tokenStore: tokenStore,
  );
  final ordersClient = OrdersClient(config: config, tokenStore: tokenStore);
  final ordersController = OrdersController(
    client: ordersClient,
    tokenStore: tokenStore,
  );
  return (
    config: config,
    tokenStore: tokenStore,
    itemsClient: itemsClient,
    itemsController: itemsController,
    categoriesController: categoriesController,
    ordersController: ordersController,
    appStateStore: appStateStore,
    stateApi: stateApi,
  );
}

/// Pump-and-settle until [predicate] returns true OR [budget]
/// elapses. `pumpAndSettle()` alone gives up after ~10 s of
/// continuous frame requests; for backends that take a moment to
/// respond we want to keep pumping past the first idle.
Future<void> _waitFor(
  WidgetTester tester,
  bool Function() predicate, {
  Duration budget = const Duration(seconds: 30),
  Duration step = const Duration(milliseconds: 200),
  String? description,
}) async {
  final deadline = DateTime.now().add(budget);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(step);
    if (predicate()) {
      return;
    }
  }
  fail('Predicate never became true within ${budget.inSeconds}s'
      '${description == null ? "" : " — $description"}');
}

void main() {
  // Switch to the LIVE binding — the default
  // `AutomatedTestWidgetsFlutterBinding` mocks the HTTP layer
  // (returns 400 for every `dart:io` request) and uses a fake
  // clock that never lets real-network futures resolve. The live
  // binding behaves like a real Flutter app: real timers, real
  // HTTP, real microtasks. It is the right choice when the test
  // deliberately hits an external backend.
  LiveTestWidgetsFlutterBinding.ensureInitialized();

  final env = Platform.environment;
  final runE2e = env['RUN_CROSS_STACK_E2E'] == '1';
  final backendUrl = env['BACKEND_URL'];

  if (!runE2e || backendUrl == null || backendUrl.isEmpty) {
    test('cross-stack e2e skipped (RUN_CROSS_STACK_E2E != 1)', () {
      expect(true, isTrue);
    });
    return;
  }

  testWidgets(
    'login → home renders → create + complete + filter toggle',
    (WidgetTester tester) async {
      // Belt-and-braces — even with the live binding, an upstream
      // test in the same isolate may have installed an HttpOverrides.
      HttpOverrides.global = null;

      // Unique item name per run so we never collide with stale
      // rows in the shared `items` table.
      final uniqueSuffix = DateTime.now().millisecondsSinceEpoch.toString();
      final itemName = 'Flutter E2E item $uniqueSuffix';

      // ── Step 0: register the test user via raw HTTP ────────────
      await _registerUser(backendUrl);

      // Wire the widget tree against the live backend. Make sure
      // the token store is empty so the first pump shows LoginScreen.
      final tree = _buildTree(backendUrl);
      tree.tokenStore.value = null;
      addTearDown(() {
        tree.tokenStore.value = null;
        tree.itemsClient.close();
      });

      await tester.pumpWidget(
        DevSkelApp(
          config: tree.config,
          tokenStore: tree.tokenStore,
          itemsClient: tree.itemsClient,
          itemsController: tree.itemsController,
          categoriesController: tree.categoriesController,
          ordersController: tree.ordersController,
          appStateStore: tree.appStateStore,
          stateApi: tree.stateApi,
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));

      // ── Step 1: LOGIN ────────────────────────────────────────
      // The LoginScreen renders a "Sign in" headline + two TextFields
      // (with InputDecoration labels). Find by label so layout
      // tweaks don't break the test.
      final usernameField = find.ancestor(
        of: find.text('Username'),
        matching: find.byType(TextField),
      );
      final passwordField = find.ancestor(
        of: find.text('Password'),
        matching: find.byType(TextField),
      );
      expect(usernameField, findsOneWidget,
          reason: 'LoginScreen Username TextField not found');
      expect(passwordField, findsOneWidget,
          reason: 'LoginScreen Password TextField not found');

      await tester.enterText(usernameField, _e2eUsername);
      await tester.enterText(passwordField, _e2ePassword);
      await tester.pump();

      final signInButton = find.widgetWithText(FilledButton, 'Sign in');
      expect(signInButton, findsOneWidget);
      await tester.tap(signInButton);

      // ── Step 2: wait for HomeScreen to render ───────────────
      // The HomeScreen renders an "Items (N…)" heading. Poll until
      // the auth round-trip + initial items fetch + state hydration
      // all complete.
      await _waitFor(
        tester,
        () => find.textContaining(RegExp(r'Items \(\d+')).evaluate().isNotEmpty,
        description: 'HomeScreen "Items (N)" heading',
      );
      expect(tree.tokenStore.isAuthenticated, isTrue,
          reason: 'login should set tokenStore.value');

      // Sign-out button is the canonical "we are on HomeScreen" tell.
      expect(find.byTooltip('Sign out'), findsOneWidget);

      // ── Step 3: CREATE an item ───────────────────────────────
      final nameField = find.ancestor(
        of: find.text('Name'),
        matching: find.byType(TextField),
      );
      expect(nameField, findsOneWidget);
      await tester.enterText(nameField, itemName);
      await tester.pump();

      final createButton = find.widgetWithText(FilledButton, 'Create item');
      expect(createButton, findsOneWidget);
      await tester.tap(createButton);
      await _waitFor(
        tester,
        () => find.text(itemName).evaluate().isNotEmpty,
        description: 'newly-created item appears in list',
      );

      // ── Step 4: COMPLETE the item ───────────────────────────
      // Find the ListTile whose subtree contains our unique item
      // name. Walk to its trailing TextButton ("Mark complete") and
      // tap it. We MUST scope the find to OUR row because earlier
      // smoke runs may have left other uncompleted items in the
      // shared table.
      final ourRow = find.ancestor(
        of: find.text(itemName),
        matching: find.byType(ListTile),
      );
      expect(ourRow, findsOneWidget,
          reason: 'ListTile for "$itemName" missing');

      final markCompleteButton = find.descendant(
        of: ourRow,
        matching: find.widgetWithText(TextButton, 'Mark complete'),
      );
      expect(markCompleteButton, findsOneWidget,
          reason: 'Mark complete button missing in our row');

      // Ensure the row is on-screen before tapping (the list lives
      // inside a SingleChildScrollView and may be partially clipped
      // when many items are present).
      await tester.ensureVisible(markCompleteButton);
      await tester.pump();
      await tester.tap(markCompleteButton);

      // After complete, the trailing TextButton should be replaced
      // by a Chip with the "✓ done" label. Scope the find to OUR
      // row so a previously-completed item's chip doesn't satisfy
      // the predicate.
      await _waitFor(
        tester,
        () {
          final row = find.ancestor(
            of: find.text(itemName),
            matching: find.byType(ListTile),
          );
          if (row.evaluate().isEmpty) return false;
          final chip = find.descendant(
            of: row,
            matching: find.widgetWithText(Chip, '✓ done'),
          );
          return chip.evaluate().isNotEmpty;
        },
        description: '✓ done Chip in our row',
      );

      // ── Step 5: FILTER toggle ────────────────────────────────
      // The "Show completed" Switch defaults to true (showing all
      // items). Toggling it off should hide the completed row.
      final switchFinder = find.byType(Switch);
      expect(switchFinder, findsOneWidget,
          reason: 'Show-completed Switch missing');
      final switchWidget = tester.widget<Switch>(switchFinder);
      expect(switchWidget.value, isTrue);

      // Invoke onChanged directly — `tester.tap` can miss under
      // LiveTestWidgetsFlutterBinding when the Switch is near an
      // edge or requires precise hit-testing. Direct invocation
      // mirrors what the user's finger triggers.
      switchWidget.onChanged!(false);
      await tester.pump(const Duration(milliseconds: 500));

      await _waitFor(
        tester,
        () => find.text(itemName).evaluate().isEmpty,
        description: 'completed item hidden after toggling Show completed off',
      );

      // Toggle back on — our completed item should reappear.
      // Re-find the Switch since the widget tree rebuilt.
      final switchWidget2 = tester.widget<Switch>(find.byType(Switch));
      switchWidget2.onChanged!(true);
      await tester.pump(const Duration(milliseconds: 500));
      await _waitFor(
        tester,
        () => find.text(itemName).evaluate().isNotEmpty,
        description: 'completed item visible again after toggling on',
      );

      // ── Step 6: ORDERS section visible ──────────────────────────
      // The HomeScreen renders an "Orders (N)" heading from the
      // OrderListView. Verify it appears after login.
      await _waitFor(
        tester,
        () => find.textContaining(RegExp(r'Orders \(\d+')).evaluate().isNotEmpty,
        description: 'HomeScreen "Orders (N)" heading',
        budget: const Duration(seconds: 15),
      );
    },
    timeout: const Timeout(Duration(seconds: 90)),
  );
}
